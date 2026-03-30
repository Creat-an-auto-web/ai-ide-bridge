import { spawn } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(frontendRoot, '..')

const backendPort = Number(process.env.BRIDGE_BACKEND_PORT ?? 27182)
const frontendPort = Number(process.env.BRIDGE_FRONTEND_PORT ?? 4310)
const pythonCommand = process.env.BRIDGE_PYTHON ?? 'python'

let backendProcess = null
let frontendProcess = null

const log = (...args) => {
  console.log('[browser-shell]', ...args)
}

const waitForHttpOk = async (url, label) => {
  const startedAt = Date.now()
  const timeoutMs = 30000

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) {
        return
      }
    } catch {
      // 进程尚未就绪时忽略
    }

    await delay(500)
  }

  throw new Error(`${label} 启动超时：${url}`)
}

const spawnLoggedProcess = (command, args, options) => {
  const child = spawn(command, args, {
    stdio: 'pipe',
    ...options,
  })

  child.stdout.on('data', (chunk) => process.stdout.write(String(chunk)))
  child.stderr.on('data', (chunk) => process.stderr.write(String(chunk)))

  return child
}

const startBackend = async () => {
  if (backendProcess) {
    return
  }

  log('启动 backend-bridge')
  backendProcess = spawnLoggedProcess(
    pythonCommand,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
    {
      cwd: path.join(projectRoot, 'backend-bridge'),
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
    },
  )

  backendProcess.on('exit', (code, signal) => {
    log(`backend-bridge 已退出 code=${code} signal=${signal}`)
    backendProcess = null
  })

  await waitForHttpOk(`http://127.0.0.1:${backendPort}/healthz`, 'backend-bridge')
}

const startFrontend = async () => {
  if (frontendProcess) {
    return
  }

  log('启动 frontend-bridge demo 服务')
  frontendProcess = spawnLoggedProcess(
    process.execPath,
    [path.join(frontendRoot, 'frontend-bridge', 'demo', 'server.mjs')],
    {
      cwd: path.join(frontendRoot, 'frontend-bridge'),
      env: {
        ...process.env,
        FRONTEND_BRIDGE_PORT: String(frontendPort),
        BACKEND_BRIDGE_HOST: '127.0.0.1',
        BACKEND_BRIDGE_PORT: String(backendPort),
      },
    },
  )

  frontendProcess.on('exit', (code, signal) => {
    log(`frontend-bridge demo 已退出 code=${code} signal=${signal}`)
    frontendProcess = null
  })

  await waitForHttpOk(`http://127.0.0.1:${frontendPort}/`, 'frontend-bridge demo')
}

const stopChild = (child) => {
  if (!child || child.killed) {
    return
  }

  child.kill('SIGINT')
}

const openUrl = async (url) => {
  const opener = spawn('xdg-open', [url], {
    stdio: 'ignore',
    detached: true,
  })

  opener.unref()
  log(`已请求系统打开界面：${url}`)
}

const main = async () => {
  await startBackend()
  await startFrontend()

  const url = `http://127.0.0.1:${frontendPort}`
  await openUrl(url)

  log('本地界面已启动。按 Ctrl+C 可结束后台进程。')
}

process.on('SIGINT', () => {
  stopChild(frontendProcess)
  stopChild(backendProcess)
  process.exit(0)
})

process.on('SIGTERM', () => {
  stopChild(frontendProcess)
  stopChild(backendProcess)
  process.exit(0)
})

await main()

await new Promise(() => {})
