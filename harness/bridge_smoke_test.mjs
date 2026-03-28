#!/usr/bin/env node

const DEFAULT_BASE_URL = process.env.BRIDGE_BASE_URL ?? 'http://127.0.0.1:27182'
const DEFAULT_MODE = process.env.BRIDGE_TASK_MODE ?? 'fix_test'
const DEFAULT_REPO = process.env.BRIDGE_REPO_PATH ?? process.cwd()
const DEFAULT_PROMPT = process.env.BRIDGE_PROMPT ?? 'Fix the current failing test'
const AUTO_APPROVE = (process.env.BRIDGE_AUTO_APPROVE ?? '1') !== '0'
const TIMEOUT_MS = Number(process.env.BRIDGE_TIMEOUT_MS ?? 30000)

const state = {
  taskId: null,
  pendingCommandId: null,
  finalEvent: null,
}

const now = () => new Date().toISOString()

const log = (...args) => {
  console.log(`[${now()}]`, ...args)
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
      reason: approved ? 'Auto-approved by smoke test' : 'Auto-rejected by smoke test',
    },
  )
  log('approval response', JSON.stringify(response, null, 2))
}

const main = async () => {
  log('creating task against', DEFAULT_BASE_URL)
  const createResponse = await postJson('/v1/tasks', buildRequest())
  log('create response', JSON.stringify(createResponse, null, 2))

  if (!createResponse.success || !createResponse.data?.task?.taskId) {
    throw new Error('Failed to create task')
  }

  state.taskId = createResponse.data.task.taskId
  const wsBase = DEFAULT_BASE_URL.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')
  const wsUrl = `${wsBase}/v1/tasks/${state.taskId}/events`
  log('connecting websocket', wsUrl)

  const ws = new WebSocket(wsUrl)
  const timeout = setTimeout(() => {
    log(`timed out after ${TIMEOUT_MS}ms`)
    ws.close()
    process.exitCode = 1
  }, TIMEOUT_MS)

  ws.onopen = () => {
    log('websocket open')
  }

  ws.onmessage = async (message) => {
    const event = JSON.parse(String(message.data))
    log('event', JSON.stringify(event, null, 2))

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
    console.error(error)
    process.exitCode = 1
  }

  ws.onclose = () => {
    clearTimeout(timeout)
    if (state.finalEvent) {
      log('completed successfully')
      process.exitCode = 0
      return
    }
    log('websocket closed before final event')
    process.exitCode = process.exitCode ?? 1
  }
}

await main()
