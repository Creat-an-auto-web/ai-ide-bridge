import { app, BrowserWindow, dialog } from 'electron'
import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(frontendRoot, '..')
const repoRoot = path.resolve(projectRoot, '..')

const backendPort = Number(process.env.BRIDGE_BACKEND_PORT ?? 27182)
const frontendPort = Number(process.env.BRIDGE_FRONTEND_PORT ?? 4310)
const pythonCommand = process.env.BRIDGE_PYTHON ?? 'python'

let backendProcess = null
let frontendProcess = null

app.disableHardwareAcceleration()
app.commandLine.appendSwitch('disable-gpu')

const log = (...args) => {
  console.log('[local-ide-shell]', ...args)
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

  child.stdout.on('data', (chunk) => {
    process.stdout.write(String(chunk))
  })
  child.stderr.on('data', (chunk) => {
    process.stderr.write(String(chunk))
  })

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

const createMainWindow = async () => {
  await startBackend()
  await startFrontend()

  const window = new BrowserWindow({
    width: 1480,
    height: 980,
    minWidth: 1100,
    minHeight: 720,
    autoHideMenuBar: true,
    title: 'AI IDE Bridge 本地界面',
    backgroundColor: '#0f1115',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  await window.loadURL(`http://127.0.0.1:${frontendPort}`)
}

app.whenReady().then(async () => {
  try {
    await createMainWindow()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    await dialog.showMessageBox({
      type: 'error',
      title: '启动失败',
      message: '本地 IDE 界面启动失败',
      detail: message,
    })
    app.exit(1)
  }

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopChild(frontendProcess)
  stopChild(backendProcess)
})

process.on('SIGINT', () => {
  stopChild(frontendProcess)
  stopChild(backendProcess)
  app.quit()
})

log(`工作区根目录: ${repoRoot}`)
