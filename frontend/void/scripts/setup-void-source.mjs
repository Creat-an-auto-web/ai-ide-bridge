import { spawn } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const VOID_REPOSITORY = 'https://github.com/voideditor/void.git'
const VOID_REVISION = '2e5ecb291d33afbe4565921664fb7e183189c1c5'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const projectRoot = path.resolve(__dirname, '..', '..', '..')
const sourceRoot = path.join(projectRoot, 'upstream', 'Void')

const exists = async (targetPath) => {
  try {
    await fs.access(targetPath)
    return true
  } catch {
    return false
  }
}

const run = async (command, args, cwd = projectRoot) => {
  const child = spawn(command, args, {
    cwd,
    stdio: 'inherit',
  })
  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('exit', (code) => resolve(code ?? 1))
  })
  if (exitCode !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit code ${exitCode}`)
  }
}

const main = async () => {
  if (await exists(path.join(sourceRoot, 'package.json'))) {
    console.log(`[void-source] Reusing ${sourceRoot}`)
    return
  }

  const gitDirectory = path.join(sourceRoot, '.git')
  if (await exists(gitDirectory)) {
    console.log(`[void-source] Resuming incomplete checkout in ${sourceRoot}`)
  } else if (await exists(sourceRoot)) {
    const entries = await fs.readdir(sourceRoot)
    if (entries.length > 0) {
      throw new Error(
        `${sourceRoot} exists but is not a complete Void checkout; move or empty it first.`,
      )
    }
  } else {
    await fs.mkdir(sourceRoot, { recursive: true })
  }

  console.log(`[void-source] Installing Void ${VOID_REVISION} into ${sourceRoot}`)
  if (!await exists(gitDirectory)) {
    await run('git', ['init'], sourceRoot)
    await run('git', ['remote', 'add', 'origin', VOID_REPOSITORY], sourceRoot)
  }
  await run('git', ['config', 'http.version', 'HTTP/1.1'], sourceRoot)
  await run('git', ['fetch', '--depth', '1', 'origin', VOID_REVISION], sourceRoot)
  await run('git', ['checkout', '--detach', 'FETCH_HEAD'], sourceRoot)
  console.log('[void-source] Void source is ready')
}

main().catch((error) => {
  console.error(`[void-source] ${error instanceof Error ? error.message : String(error)}`)
  process.exitCode = 1
})
