import { build } from 'esbuild'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const projectRoot = path.resolve(__dirname, '..')
const distRoot = path.join(projectRoot, 'dist')

await fs.mkdir(distRoot, { recursive: true })

await build({
  entryPoints: [path.join(projectRoot, 'src', 'local-host', 'index.tsx')],
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: ['chrome128'],
  outfile: path.join(distRoot, 'app.js'),
  jsx: 'automatic',
  sourcemap: true,
  loader: {
    '.ts': 'ts',
    '.tsx': 'tsx',
    '.css': 'css',
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  logLevel: 'info',
})

await fs.writeFile(
  path.join(distRoot, 'index.html'),
  `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI IDE Bridge 本地 IDE</title>
    <link rel="stylesheet" href="./app.css" />
    <script type="module" src="./app.js"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
`,
  'utf8',
)

console.log(`void 本地前端已构建到 ${distRoot}`)
