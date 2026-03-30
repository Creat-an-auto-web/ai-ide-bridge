#!/usr/bin/env node

import net from 'node:net'
import tls from 'node:tls'

const DEFAULT_BASE_URL = process.env.BRIDGE_BASE_URL ?? 'http://127.0.0.1:27182'
const DEFAULT_MODE = process.env.BRIDGE_TASK_MODE ?? 'fix_test'
const DEFAULT_REPO = process.env.BRIDGE_REPO_PATH ?? process.cwd()
const DEFAULT_PROMPT = process.env.BRIDGE_PROMPT ?? '修复当前失败的测试'
const AUTO_APPROVE = (process.env.BRIDGE_AUTO_APPROVE ?? '1') !== '0'
const TIMEOUT_MS = Number(process.env.BRIDGE_TIMEOUT_MS ?? 30000)

const state = {
  taskId: null,
  pendingCommandId: null,
  finalEvent: null,
  failureReason: null,
}

const now = () => new Date().toISOString()

const log = (...args) => {
  console.log(`[${now()}]`, ...args)
}

const probeWebSocketUpgrade = async (wsUrl) => {
  const target = new URL(wsUrl)
  const isSecure = target.protocol === 'wss:'
  const port = Number(target.port || (isSecure ? '443' : '80'))
  const key = Buffer.from(`probe_${Math.random().toString(16).slice(2, 10)}`).toString('base64')

  return await new Promise((resolve) => {
    let settled = false
    let raw = ''

    const finish = (result) => {
      if (settled) {
        return
      }
      settled = true
      socket.destroy()
      resolve(result)
    }

    const socket = isSecure
      ? tls.connect(
          {
            host: target.hostname,
            port,
            servername: target.hostname,
          },
          sendHandshake,
        )
      : net.connect(
          {
            host: target.hostname,
            port,
          },
          sendHandshake,
        )

    socket.setTimeout(3000, () => {
      finish({
        ok: false,
        reason: 'timeout',
      })
    })

    socket.on('error', (error) => {
      finish({
        ok: false,
        reason: 'socket_error',
        message: error.message,
      })
    })

    socket.on('data', (chunk) => {
      raw += chunk.toString('utf8')
      if (!raw.includes('\r\n\r\n')) {
        return
      }

      const [head, body = ''] = raw.split('\r\n\r\n')
      const lines = head.split('\r\n')
      const statusLine = lines[0] ?? ''
      const statusCode = Number(statusLine.split(' ')[1] ?? 0)

      finish({
        ok: statusCode === 101,
        reason: statusCode === 101 ? 'upgrade_ok' : 'unexpected_status',
        statusCode,
        statusLine,
        headers: lines.slice(1),
        body,
      })
    })

    function sendHandshake() {
      socket.write(
        [
          `GET ${target.pathname}${target.search} HTTP/1.1`,
          `Host: ${target.host}`,
          'Upgrade: websocket',
          'Connection: Upgrade',
          `Sec-WebSocket-Key: ${key}`,
          'Sec-WebSocket-Version: 13',
          '',
          '',
        ].join('\r\n'),
      )
    }
  })
}

const buildRequest = () => ({
  requestId: `req_${Math.random().toString(16).slice(2, 10)}`,
  protocolVersion: 'v1alpha1',
  mode: DEFAULT_MODE,
  userPrompt: DEFAULT_PROMPT,
  repo: {
    rootPath: DEFAULT_REPO,
  },
  context: {
    activeFile: undefined,
    selection: null,
    openFiles: [],
    diagnostics: [],
    gitDiff: '',
    terminalTail: '',
    testLogs: '',
  },
  policy: {
    workspaceMode: 'local',
    network: 'deny',
    requireApprovalFor: ['package_install', 'destructive_command', 'git_push'],
    maxDurationSec: 600,
    maxOutputBytes: 262144,
    writablePaths: [],
    envAllowlist: [],
  },
})

const postJson = async (path, body) => {
  const response = await fetch(`${DEFAULT_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return await response.json()
}

const approveCommand = async (taskId, commandId, approved) => {
  const response = await postJson(
    `/v1/tasks/${taskId}/commands/${commandId}/approval`,
    {
      approved,
      reason: approved ? '由 smoke test 自动批准' : '由 smoke test 自动拒绝',
    },
  )
  log('审批响应', JSON.stringify(response, null, 2))
}

const main = async () => {
  log('正在向后端创建任务', DEFAULT_BASE_URL)
  const createResponse = await postJson('/v1/tasks', buildRequest())
  log('创建任务响应', JSON.stringify(createResponse, null, 2))

  if (!createResponse.success || !createResponse.data?.task?.taskId) {
    throw new Error('创建任务失败')
  }

  state.taskId = createResponse.data.task.taskId
  const wsBase = DEFAULT_BASE_URL.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')
  const wsUrl = `${wsBase}/v1/tasks/${state.taskId}/events`
  log('正在连接 WebSocket', wsUrl)

  const ws = new WebSocket(wsUrl)
  const timeout = setTimeout(() => {
    log(`等待超时，已超过 ${TIMEOUT_MS}ms`)
    ws.close()
    process.exitCode = 1
  }, TIMEOUT_MS)

  ws.onopen = () => {
    log('WebSocket 已连接')
  }

  ws.onmessage = async (message) => {
    const event = JSON.parse(String(message.data))
    log('收到事件', JSON.stringify(event, null, 2))

    if (event.type === 'task.command.request') {
      state.pendingCommandId = event.payload.commandId
      if (AUTO_APPROVE) {
        await approveCommand(state.taskId, state.pendingCommandId, true)
      }
    }

    if (event.type === 'task.final') {
      state.finalEvent = event
      clearTimeout(timeout)
      ws.close()
    }
  }

  ws.onerror = (error) => {
    clearTimeout(timeout)
    state.failureReason = 'websocket_error'
    console.error(error)
    void (async () => {
      const probe = await probeWebSocketUpgrade(wsUrl)
      log('WebSocket 升级探测结果', JSON.stringify(probe, null, 2))

      if (probe.statusCode === 404) {
        console.error(
          'WebSocket 升级返回了 404。后端大概率缺少 WebSocket 支持。如果你在使用 uvicorn，请安装 `websockets` 或 `wsproto`，然后重启服务。',
        )
      }

      process.exitCode = 1
    })()
  }

  ws.onclose = () => {
    clearTimeout(timeout)
    if (state.finalEvent) {
      log('执行完成')
      process.exitCode = 0
      return
    }
    log('在收到最终事件前 WebSocket 已关闭', state.failureReason ?? 'unknown_reason')
    process.exitCode = process.exitCode ?? 1
  }
}

await main()
