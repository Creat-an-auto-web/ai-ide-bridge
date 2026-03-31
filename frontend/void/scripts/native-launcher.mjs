import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const voidPatchRoot = path.resolve(__dirname, '..')
const frontendRoot = path.resolve(voidPatchRoot, '..')
const projectRoot = path.resolve(frontendRoot, '..')
const repoRoot = path.resolve(projectRoot, '..')

const sourceVoidRoot = path.join(repoRoot, 'void')
const sourceFrontendBridgeRoot = path.join(frontendRoot, 'frontend-bridge')
const runtimeRoot = path.join(frontendRoot, '.runtime', 'void-native')
const runtimeVoidRoot = path.join(runtimeRoot, 'void')
const runtimeFrontendBridgeRoot = path.join(runtimeVoidRoot, 'src', 'ai-ide-bridge', 'frontend-bridge')
const runtimeMarkerFile = path.join(runtimeRoot, 'runtime.json')
const runtimeUserDataDir = path.join(runtimeRoot, 'user-data')
const runtimeExtensionsDir = path.join(runtimeRoot, 'extensions')

const backendPort = Number(process.env.BRIDGE_BACKEND_PORT ?? 27182)
const shouldAutoStartBackend = process.env.BRIDGE_BACKEND_AUTO_START !== '0'
const shouldStartWatchProcesses = process.env.BRIDGE_START_WATCHERS === '1'
const npmCommand = process.env.BRIDGE_NPM ?? 'npm'
const runtimeExtraPackages = [
  'ternary-stream',
  'gulp-sort',
  'gulp-merge-json',
  'jsonc-parser',
  'byline',
  'vscode-gulp-watch',
  'binaryextensions',
  'textextensions',
]
const runtimeWorkspaceDependencyProbeDirs = [
  path.join('extensions', 'extension-editing', 'node_modules'),
  path.join('extensions', 'css-language-features', 'server', 'node_modules'),
  path.join('extensions', 'html-language-features', 'server', 'node_modules'),
]
const runtimeExtensionInstallDirs = [
  'extensions',
  'extensions/configuration-editing',
  'extensions/css-language-features',
  'extensions/css-language-features/server',
  'extensions/debug-auto-launch',
  'extensions/debug-server-ready',
  'extensions/emmet',
  'extensions/extension-editing',
  'extensions/git',
  'extensions/git-base',
  'extensions/github',
  'extensions/github-authentication',
  'extensions/grunt',
  'extensions/gulp',
  'extensions/html-language-features',
  'extensions/html-language-features/server',
  'extensions/ipynb',
  'extensions/jake',
  'extensions/json-language-features',
  'extensions/json-language-features/server',
  'extensions/markdown-language-features',
  'extensions/markdown-math',
  'extensions/media-preview',
  'extensions/merge-conflict',
  'extensions/microsoft-authentication',
  'extensions/notebook-renderers',
  'extensions/npm',
  'extensions/php-language-features',
  'extensions/references-view',
  'extensions/search-result',
  'extensions/simple-browser',
  'extensions/tunnel-forwarding',
  'extensions/typescript-language-features',
  'extensions/vscode-api-tests',
  'extensions/vscode-colorize-tests',
  'extensions/vscode-colorize-perf-tests',
  'extensions/vscode-test-resolver',
  '.vscode/extensions/vscode-selfhost-import-aid',
  '.vscode/extensions/vscode-selfhost-test-provider',
  'extensions/open-remote-ssh',
  'extensions/open-remote-wsl',
]

const childProcesses = new Set()

const log = (...args) => {
  console.log('[void-native-launcher]', ...args)
}

const exists = async (targetPath) => {
  try {
    await fs.access(targetPath)
    return true
  } catch {
    return false
  }
}

const ensureDir = async (targetPath) => {
  await fs.mkdir(targetPath, { recursive: true })
}

const resolvePythonCommand = async () => {
  if (process.env.BRIDGE_PYTHON) {
    return process.env.BRIDGE_PYTHON
  }

  const candidatePaths = [
    path.join(repoRoot, '.venv', 'bin', 'python'),
    path.join(projectRoot, '.venv', 'bin', 'python'),
  ]

  for (const candidatePath of candidatePaths) {
    if (await exists(candidatePath)) {
      return candidatePath
    }
  }

  return 'python'
}

const readFileIfExists = async (targetPath) => {
  try {
    return await fs.readFile(targetPath, 'utf8')
  } catch {
    return ''
  }
}

const isWslEnvironment = async () => {
  if (process.env.WSL_DISTRO_NAME || process.env.WSL_INTEROP) {
    return true
  }

  if (await exists('/mnt/wslg/versions.txt')) {
    return true
  }

  const procVersion = await readFileIfExists('/proc/version')
  return /microsoft/i.test(procVersion)
}

const readRequiredNodeVersion = async () => {
  const nvmrcPath = path.join(sourceVoidRoot, '.nvmrc')
  if (!await exists(nvmrcPath)) {
    return '20.18.2'
  }
  return (await fs.readFile(nvmrcPath, 'utf8')).trim() || '20.18.2'
}

const ensureSupportedNodeVersion = async () => {
  const required = await readRequiredNodeVersion()
  const current = process.versions.node

  if (current === required) {
    return
  }

  const currentMajor = Number(current.split('.')[0] ?? '0')
  const requiredMajor = Number(required.split('.')[0] ?? '0')

  if (currentMajor !== requiredMajor) {
    throw new Error(
      [
        `当前 Node 版本为 ${current}，但 Void 要求 ${required}。`,
        '请先切换到 Void 要求的 Node 版本后再执行本启动器。',
      ].join('\n'),
    )
  }

  log(`警告：当前 Node 版本为 ${current}，Void 推荐版本为 ${required}`)
}

const shouldSkipCopyEntry = (entryPath) => {
  const base = path.basename(entryPath)
  return base === '.git' || base === 'node_modules' || base === 'out' || base === '.build'
}

const copyTree = async (sourcePath, targetPath) => {
  await fs.cp(sourcePath, targetPath, {
    recursive: true,
    force: true,
    filter: (entryPath) => !shouldSkipCopyEntry(entryPath),
  })
}

const patchRuntimeFileText = async (relativePath, replacer) => {
  const filePath = path.join(runtimeVoidRoot, relativePath)
  if (!await exists(filePath)) {
    return
  }

  const original = await fs.readFile(filePath, 'utf8')
  const next = replacer(original)
  if (next !== original) {
    await fs.writeFile(filePath, next, 'utf8')
  }
}

const ensureRuntimeExecutable = async (relativePath) => {
  const filePath = path.join(runtimeVoidRoot, relativePath)
  if (!await exists(filePath)) {
    return
  }
  await fs.chmod(filePath, 0o755)
}

const ensureRuntimeBinExecutables = async () => {
  const binDir = path.join(runtimeVoidRoot, 'node_modules', '.bin')
  if (!await exists(binDir)) {
    return
  }

  for (const entry of await fs.readdir(binDir)) {
    const linkPath = path.join(binDir, entry)
    let targetPath = linkPath

    try {
      const stats = await fs.lstat(linkPath)
      if (stats.isSymbolicLink()) {
        const resolved = await fs.readlink(linkPath)
        targetPath = path.resolve(path.dirname(linkPath), resolved)
      }
      await fs.chmod(targetPath, 0o755)
    } catch {
      // 忽略不可修正的入口，实际执行时再暴露
    }
  }
}

const applyRuntimeFixes = async () => {
  await patchRuntimeFileText(
    path.join('build', 'lib', 'tsb', 'builder.js'),
    (text) => text.replaceAll('.bgcyan(', '.bgCyan('),
  )
  await patchRuntimeFileText(
    path.join('build', 'lib', 'tsb', 'builder.ts'),
    (text) => text.replaceAll('.bgcyan(', '.bgCyan('),
  )
  await ensureRuntimeExecutable(path.join('node_modules', 'tailwindcss', 'lib', 'cli.js'))
  await ensureRuntimeExecutable(path.join('node_modules', 'scope-tailwind', 'dist', 'main.js'))
  await ensureRuntimeExecutable(path.join('node_modules', 'tsup', 'dist', 'cli-default.js'))
  await ensureRuntimeBinExecutables()
}

const writeRuntimeMarker = async () => {
  const marker = {
    sourceVoidRoot,
    sourceFrontendBridgeRoot,
    generatedAt: new Date().toISOString(),
  }
  await fs.writeFile(runtimeMarkerFile, JSON.stringify(marker, null, 2), 'utf8')
}

const prepareRuntime = async ({ fresh = false } = {}) => {
  if (!await exists(path.join(sourceVoidRoot, 'package.json'))) {
    throw new Error(`未找到原始 Void 工程：${sourceVoidRoot}`)
  }

  if (!await exists(path.join(sourceFrontendBridgeRoot, 'src', 'index.ts'))) {
    throw new Error(`未找到 frontend-bridge 源码：${sourceFrontendBridgeRoot}`)
  }

  await ensureDir(runtimeRoot)

  if (fresh) {
    log('清理旧的运行时副本')
    await fs.rm(runtimeVoidRoot, { recursive: true, force: true })
    await fs.rm(runtimeFrontendBridgeRoot, { recursive: true, force: true })
  }

  if (!await exists(runtimeVoidRoot)) {
    log(`创建 Void 运行时副本: ${runtimeVoidRoot}`)
    await copyTree(sourceVoidRoot, runtimeVoidRoot)
  } else {
    log(`复用已有 Void 运行时副本: ${runtimeVoidRoot}`)
  }

  log('覆盖 frontend/void 补丁文件到运行时副本')
  await copyTree(path.join(voidPatchRoot, 'src'), path.join(runtimeVoidRoot, 'src'))

  log('映射 frontend-bridge 源码到运行时目录')
  await copyTree(path.join(sourceFrontendBridgeRoot, 'src'), path.join(runtimeFrontendBridgeRoot, 'src'))
  await applyRuntimeFixes()

  await ensureDir(runtimeUserDataDir)
  await ensureDir(runtimeExtensionsDir)
  await writeRuntimeMarker()

  return {
    runtimeVoidRoot,
    runtimeFrontendBridgeRoot,
  }
}

const spawnLogged = (command, args, options = {}) => {
  const child = spawn(command, args, {
    cwd: options.cwd,
    env: options.env ?? process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  childProcesses.add(child)
  child.on('exit', () => {
    childProcesses.delete(child)
  })

  const prefix = options.prefix ? `[${options.prefix}] ` : ''
  child.stdout.on('data', (chunk) => {
    process.stdout.write(`${prefix}${String(chunk)}`)
  })
  child.stderr.on('data', (chunk) => {
    process.stderr.write(`${prefix}${String(chunk)}`)
  })

  return child
}

const runToCompletion = async (command, args, options = {}) => {
  const child = spawnLogged(command, args, options)

  const exitCode = await new Promise((resolve, reject) => {
    child.on('error', reject)
    child.on('exit', (code) => resolve(code ?? 1))
  })

  if (exitCode !== 0) {
    throw new Error(`${options.label ?? command} 执行失败，退出码 ${exitCode}`)
  }
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
      // 尚未就绪时忽略
    }

    await delay(500)
  }

  throw new Error(`${label} 启动超时：${url}`)
}

const isHttpOk = async (url) => {
  try {
    const response = await fetch(url)
    return response.ok
  } catch {
    return false
  }
}

const ensureBackend = async () => {
  const healthUrl = `http://127.0.0.1:${backendPort}/healthz`

  if (await isHttpOk(healthUrl)) {
    log('复用已存在的 backend-bridge')
    return null
  }

  if (!shouldAutoStartBackend) {
    throw new Error(
      [
        `未检测到 backend-bridge：${healthUrl}`,
        '当前已关闭自动启动，请先手动启动 backend-bridge，或移除 BRIDGE_BACKEND_AUTO_START=0。',
      ].join('\n'),
    )
  }

  log('启动 backend-bridge')
  const pythonCommand = await resolvePythonCommand()

  const child = spawnLogged(
    pythonCommand,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
    {
      cwd: path.join(projectRoot, 'backend-bridge'),
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
      prefix: 'backend-bridge',
      label: 'backend-bridge',
    },
  )
  let exited = false
  let exitCode = 0

  child.once('exit', (code) => {
    exited = true
    exitCode = code ?? 1
  })

  try {
    await waitForHttpOk(healthUrl, 'backend-bridge')
    log('backend-bridge 已就绪')
    return child
  } catch (error) {
    if (exited && await isHttpOk(healthUrl)) {
      log('检测到已有 backend-bridge 占用目标端口，切换为复用现有实例')
      return null
    }

    if (exited) {
      throw new Error(`backend-bridge 提前退出，退出码 ${exitCode}`)
    }

    throw error
  }
}

const ensureRuntimeDependenciesInstalled = async () => {
  if (!await exists(path.join(runtimeVoidRoot, 'node_modules'))) {
    throw new Error(
      [
        '运行时 Void 依赖尚未安装。',
        '请先执行：',
        'npm run install:native-deps --prefix ai-ide-bridge/frontend/void',
      ].join('\n'),
    )
  }
}

const readMtimeMs = async (targetPath) => {
  try {
    const stats = await fs.stat(targetPath)
    return stats.mtimeMs
  } catch {
    return 0
  }
}

const installRuntimeDependencies = async () => {
  await ensureSupportedNodeVersion()
  await prepareRuntime()
  log('安装运行时 Void 依赖')
  await runToCompletion(
    npmCommand,
    ['install'],
    {
      cwd: runtimeVoidRoot,
      prefix: 'void-install',
      label: 'npm install',
    },
  )
  await installRuntimeWorkspaceDependencies()
  await installRuntimeExtraPackages()
  log('运行时 Void 依赖安装完成')
}

const installRuntimeWorkspaceDependencies = async () => {
  const hasWorkspaceDeps = await Promise.all(
    runtimeWorkspaceDependencyProbeDirs.map((relativePath) =>
      exists(path.join(runtimeVoidRoot, relativePath)),
    ),
  )

  if (hasWorkspaceDeps.every(Boolean)) {
    return
  }

  for (const relativeDir of runtimeExtensionInstallDirs) {
    const packageJsonPath = path.join(runtimeVoidRoot, relativeDir, 'package.json')
    if (!await exists(packageJsonPath)) {
      continue
    }

    const nodeModulesPath = path.join(runtimeVoidRoot, relativeDir, 'node_modules')
    if (await exists(nodeModulesPath)) {
      continue
    }

    log(`安装子目录依赖: ${relativeDir}`)
    await runToCompletion(
      npmCommand,
      ['install'],
      {
        cwd: path.join(runtimeVoidRoot, relativeDir),
        prefix: `void-subdeps:${relativeDir}`,
        label: `npm install (${relativeDir})`,
      },
    )
  }
}

const installRuntimeExtraPackages = async () => {
  const hasAllPackages = await Promise.all(
    runtimeExtraPackages.map((packageName) =>
      exists(path.join(runtimeVoidRoot, 'node_modules', packageName)),
    ),
  )

  if (hasAllPackages.every(Boolean)) {
    return
  }

  log(`补装 Void 运行时额外依赖: ${runtimeExtraPackages.join(', ')}`)
  await runToCompletion(
    npmCommand,
    ['install', '--no-save', ...runtimeExtraPackages],
    {
      cwd: runtimeVoidRoot,
      prefix: 'void-extra-deps',
      label: 'npm install --no-save',
    },
  )
}

const buildRuntimeReact = async () => {
  await ensureSupportedNodeVersion()
  await prepareRuntime()
  await ensureRuntimeDependenciesInstalled()
  await installRuntimeWorkspaceDependencies()
  await installRuntimeExtraPackages()
  log('构建 Void React 前端')
  await runToCompletion(
    npmCommand,
    ['run', 'buildreact'],
    {
      cwd: runtimeVoidRoot,
      prefix: 'void-buildreact',
      label: 'npm run buildreact',
      env: {
        ...process.env,
        NODE_OPTIONS: process.env.NODE_OPTIONS ?? '--max-old-space-size=8192',
      },
    },
  )
}

const ensureRuntimeCompiled = async () => {
  const runtimeEntryFile = path.join(runtimeVoidRoot, 'out', 'main.js')
  const markerMtimeMs = await readMtimeMs(runtimeMarkerFile)
  const entryMtimeMs = await readMtimeMs(runtimeEntryFile)

  if (entryMtimeMs > markerMtimeMs) {
    log('复用已有 Void 客户端编译产物')
    return
  }

  log('构建 Void 客户端主进程产物')
  await runToCompletion(
    npmCommand,
    ['run', 'compile'],
    {
      cwd: runtimeVoidRoot,
      prefix: 'void-compile',
      label: 'npm run compile',
      env: {
        ...process.env,
        NODE_OPTIONS: process.env.NODE_OPTIONS ?? '--max-old-space-size=8192',
      },
    },
  )
}

const startRuntimeWatch = () => {
  log('后台启动 Void watch 编译进程')
  const watchChild = spawnLogged(
    npmCommand,
    ['run', 'watch'],
    {
      cwd: runtimeVoidRoot,
      prefix: 'void-watch',
      label: 'npm run watch',
      env: {
        ...process.env,
        NODE_OPTIONS: process.env.NODE_OPTIONS ?? '--max-old-space-size=8192',
      },
    },
  )

  watchChild.on('exit', (code) => {
    if (code === 0 || code === null) {
      return
    }
    console.error(`[void-native-launcher] 后台 watch 进程已退出，退出码 ${code}`)
  })

  return watchChild
}

const startVoidNative = async () => {
  await ensureSupportedNodeVersion()
  await prepareRuntime()
  await ensureRuntimeDependenciesInstalled()
  await installRuntimeWorkspaceDependencies()
  await installRuntimeExtraPackages()
  await ensureBackend()
  await buildRuntimeReact()
  await ensureRuntimeCompiled()

  log('Void 原生前端启动条件已满足，准备启动原生前端')

  const scriptPath = path.join(runtimeVoidRoot, 'scripts', 'code.sh')
  await fs.chmod(scriptPath, 0o755)

  const codeArgs = [
    '--user-data-dir',
    runtimeUserDataDir,
    '--extensions-dir',
    runtimeExtensionsDir,
  ]

  if (process.env.BRIDGE_ELECTRON_NO_SANDBOX === '1' || await isWslEnvironment()) {
    codeArgs.push('--no-sandbox')
  }

  const codeChild = spawnLogged(
    scriptPath,
    codeArgs,
    {
      cwd: runtimeVoidRoot,
      prefix: 'void-code',
      label: './scripts/code.sh',
      env: {
        ...process.env,
        BROWSER: 'none',
      },
    },
  )
  let watchChild = null

  if (shouldStartWatchProcesses) {
    void delay(15000).then(() => {
      if (codeChild.exitCode !== null) {
        return
      }
      watchChild = startRuntimeWatch()
    })
  }

  const exitCode = await new Promise((resolve, reject) => {
    codeChild.on('error', reject)
    codeChild.on('exit', (code) => resolve(code ?? 1))
  })

  if (watchChild?.exitCode === null) {
    watchChild.kill('SIGINT')
  }

  if (exitCode !== 0) {
    throw new Error(`Void 原生前端退出，退出码 ${exitCode}`)
  }
}

const stopAllChildren = () => {
  for (const child of childProcesses) {
    if (child.exitCode === null && !child.killed) {
      child.kill('SIGINT')
    }
  }
}

process.on('SIGINT', () => {
  stopAllChildren()
  process.exit(130)
})

process.on('SIGTERM', () => {
  stopAllChildren()
  process.exit(143)
})

const command = process.argv[2] ?? 'start'

try {
  if (command === 'prepare-runtime') {
    await prepareRuntime({ fresh: process.argv.includes('--fresh') })
    log(`运行时副本已就绪：${runtimeVoidRoot}`)
  } else if (command === 'install-deps') {
    await installRuntimeDependencies()
  } else if (command === 'build-react') {
    await buildRuntimeReact()
  } else if (command === 'start') {
    await startVoidNative()
  } else {
    throw new Error(`不支持的命令：${command}`)
  }
} catch (error) {
  stopAllChildren()
  const message = error instanceof Error ? error.message : String(error)
  console.error('[void-native-launcher] 启动失败:', message)
  process.exit(1)
}
