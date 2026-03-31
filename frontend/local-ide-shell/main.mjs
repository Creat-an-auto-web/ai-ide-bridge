import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(frontendRoot, '..')
const repoRoot = path.resolve(projectRoot, '..')
const voidRoot = path.join(frontendRoot, 'void')
const preloadPath = path.join(__dirname, 'preload.cjs')
const loadingHtml = [
  '<!doctype html>',
  '<html lang="zh-CN">',
  '<body style="margin:0;background:#0f1115;color:#e6edf6;font-family:sans-serif;padding:24px">',
  '<h2 style="margin:0 0 12px">AI IDE Bridge</h2>',
  '<div>本地 IDE 正在启动，请稍候...</div>',
  '</body>',
  '</html>',
].join('')
const loadingUrl = `data:text/html;charset=utf-8,${encodeURIComponent(loadingHtml)}`

const backendPort = Number(process.env.BRIDGE_BACKEND_PORT ?? 27182)
const pythonCommand = process.env.BRIDGE_PYTHON ?? 'python'
const nodeCommand = process.env.BRIDGE_NODE ?? 'node'

let backendProcess = null
let mainWindow = null

app.disableHardwareAcceleration()
app.commandLine.appendSwitch('disable-gpu')
app.commandLine.appendSwitch('disable-gpu-compositing')
app.commandLine.appendSwitch('disable-software-rasterizer')
app.commandLine.appendSwitch('no-sandbox')
app.commandLine.appendSwitch('ozone-platform', 'x11')

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

const buildVoidFrontend = async () => {
  log('构建 frontend/void 本地前端')
  const builder = spawnLoggedProcess(
    nodeCommand,
    [path.join(voidRoot, 'scripts', 'build.mjs')],
    {
      cwd: voidRoot,
      env: {
        ...process.env,
      },
    },
  )

  const exitCode = await new Promise((resolve, reject) => {
    builder.on('error', reject)
    builder.on('exit', (code) => resolve(code ?? 1))
  })

  if (exitCode !== 0) {
    throw new Error(`frontend/void 构建失败，退出码 ${exitCode}`)
  }

  log('frontend/void 构建进程已退出')

  const entryFile = path.join(voidRoot, 'dist', 'index.html')
  await fs.access(entryFile)
  log(`frontend/void 入口文件可访问: ${entryFile}`)
  return entryFile
}

const stopChild = (child) => {
  if (!child || child.killed) {
    return
  }

  child.kill('SIGINT')
}

const ensureMainWindow = async () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.focus()
    return mainWindow
  }

  log('准备创建 BrowserWindow')
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    autoHideMenuBar: true,
    title: 'AI IDE Bridge 本地界面',
    backgroundColor: '#0f1115',
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow = window

  log('BrowserWindow 已创建')

  window.once('ready-to-show', () => {
    log('本地 IDE 窗口 ready-to-show')
    window.show()
    window.focus()
  })

  window.on('closed', () => {
    log('本地 IDE 窗口已关闭')
    if (mainWindow === window) {
      mainWindow = null
    }
  })

  window.on('show', () => {
    log('本地 IDE 窗口 show')
  })

  window.webContents.on('render-process-gone', (_event, details) => {
    log(`渲染进程退出 reason=${details.reason} code=${details.exitCode}`)
  })

  window.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    log(`renderer console level=${level} ${sourceId}:${line} ${message}`)
  })

  window.webContents.on('did-finish-load', () => {
    log(`窗口页面已加载: ${window.webContents.getURL()}`)
  })

  window.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    log(`本地 IDE 界面加载失败 code=${errorCode} detail=${errorDescription}`)
  })

  await window.loadURL(loadingUrl)
  log('占位窗口页面已加载')
  return window
}

const bootstrapMainWindow = async () => {
  const window = await ensureMainWindow()
  log('开始准备本地 IDE 页面资源')
  await startBackend()
  log('backend-bridge 已就绪')
  const entryFile = await buildVoidFrontend()
  log(`frontend/void 入口文件已就绪: ${entryFile}`)
  await window.loadFile(entryFile)
  window.show()
  window.focus()
}

ipcMain.handle('ai-ide-desktop:get-initial-state', async () => ({
  repoRootPath: repoRoot,
  openFilesText: '',
  activeFile: '',
}))

ipcMain.handle('ai-ide-desktop:pick-directory', async () => {
  const window = BrowserWindow.getFocusedWindow()
  const result = await dialog.showOpenDialog(window ?? undefined, {
    title: '选择仓库目录',
    properties: ['openDirectory'],
  })
  return result.canceled ? null : result.filePaths[0] ?? null
})

ipcMain.handle('ai-ide-desktop:pick-file', async () => {
  const window = BrowserWindow.getFocusedWindow()
  const result = await dialog.showOpenDialog(window ?? undefined, {
    title: '选择当前文件',
    properties: ['openFile'],
    defaultPath: repoRoot,
  })
  return result.canceled ? null : result.filePaths[0] ?? null
})

app.whenReady().then(async () => {
  log('Electron 应用已 ready')
  try {
    await bootstrapMainWindow()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    log(`启动失败: ${message}`)
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
      await bootstrapMainWindow()
    }
  })
})

app.on('browser-window-created', () => {
  log('收到 browser-window-created 事件')
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  log('Electron 应用即将退出')
  stopChild(backendProcess)
})

app.on('will-quit', () => {
  log('Electron 应用 will-quit')
})

app.on('quit', () => {
  log('Electron 应用 quit')
})

process.on('uncaughtException', (error) => {
  log(`uncaughtException: ${error.stack ?? error.message}`)
})

process.on('unhandledRejection', (reason) => {
  log(`unhandledRejection: ${String(reason)}`)
})

process.on('SIGINT', () => {
  stopChild(backendProcess)
  app.quit()
})

log(`工作区根目录: ${repoRoot}`)
