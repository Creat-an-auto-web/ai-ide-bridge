#!/usr/bin/env node

import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const PORT = Number(process.env.FRONTEND_BRIDGE_PORT ?? 4310)
const BACKEND_PORT = Number(process.env.BACKEND_BRIDGE_PORT ?? 27182)
const BACKEND_HOST = process.env.BACKEND_BRIDGE_HOST ?? '127.0.0.1'
const DEMO_DIR = __dirname

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
}

const serveFile = (req, res) => {
  const requestPath = req.url === '/' ? '/index.html' : new URL(req.url, `http://${req.headers.host}`).pathname
  const normalized = path.normalize(requestPath).replace(/^(\.\.[/\\])+/, '')
  const filePath = path.join(DEMO_DIR, normalized)

  if (!filePath.startsWith(DEMO_DIR)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404)
      res.end('Not Found')
      return
    }
    const ext = path.extname(filePath)
    res.writeHead(200, { 'Content-Type': MIME[ext] ?? 'application/octet-stream' })
    res.end(data)
  })
}

const proxyHttp = (req, res) => {
  const upstream = http.request({
    host: BACKEND_HOST,
    port: BACKEND_PORT,
    method: req.method,
    path: req.url,
    headers: req.headers,
  }, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode ?? 502, upstreamRes.headers)
    upstreamRes.pipe(res)
  })

  upstream.on('error', (error) => {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({ success: false, error: String(error) }))
  })

  req.pipe(upstream)
}

const server = http.createServer((req, res) => {
  if (!req.url) {
    res.writeHead(400)
    res.end('Bad Request')
    return
  }

  if (req.url.startsWith('/v1/')) {
    proxyHttp(req, res)
    return
  }

  serveFile(req, res)
})

server.on('upgrade', (req, socket, head) => {
  if (!req.url?.startsWith('/v1/')) {
    socket.destroy()
    return
  }

  const upstreamSocket = net.connect(BACKEND_PORT, BACKEND_HOST, () => {
    const lines = [
      `GET ${req.url} HTTP/1.1`,
      `Host: ${BACKEND_HOST}:${BACKEND_PORT}`,
      ...Object.entries(req.headers).map(([key, value]) => `${key}: ${value}`),
      '',
      '',
    ]
    upstreamSocket.write(lines.join('\r\n'))
    if (head.length > 0) {
      upstreamSocket.write(head)
    }
    socket.pipe(upstreamSocket)
    upstreamSocket.pipe(socket)
  })

  upstreamSocket.on('error', () => socket.destroy())
  socket.on('error', () => upstreamSocket.destroy())
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`frontend-bridge demo listening on http://127.0.0.1:${PORT}`)
  console.log(`proxying /v1 and websocket traffic to http://${BACKEND_HOST}:${BACKEND_PORT}`)
})
