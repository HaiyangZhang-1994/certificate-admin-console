import { spawn } from 'node:child_process'
import path from 'node:path'
import { python, root } from './lib.mjs'

const children = []
let stopping = false

function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) child.kill('SIGTERM')
  process.exitCode = code
}

try {
  function port(name, fallback) {
    const value = process.env[name] ?? String(fallback)
    if (!/^\d+$/.test(value) || Number(value) < 1 || Number(value) > 65535) {
      throw new Error(`${name} must be an integer from 1 to 65535.`)
    }
    return String(Number(value))
  }
  const backendPort = port('BACKEND_PORT', 8000)
  const frontendPort = port('FRONTEND_PORT', 5173)
  if (backendPort === frontendPort) throw new Error('BACKEND_PORT and FRONTEND_PORT must differ.')
  const frontendUrl = `http://127.0.0.1:${frontendPort}`
  const backendUrl = `http://127.0.0.1:${backendPort}`
  const env = {
    ...process.env,
    API_PROXY_TARGET: process.env.API_PROXY_TARGET ?? backendUrl,
    ALLOWED_ORIGINS: process.env.ALLOWED_ORIGINS ?? frontendUrl,
  }
  const commands = [
    [python(), ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', backendPort], root],
    [process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', frontendPort], path.join(root, 'frontend')],
  ]
  for (const [command, args, cwd] of commands) {
    const child = spawn(command, args, { cwd, env, stdio: 'inherit' })
    children.push(child)
    child.on('error', (error) => { console.error(error.message); stop(1) })
    child.on('exit', (code) => { if (!stopping) stop(code ?? 1) })
  }
  process.on('SIGINT', () => stop())
  process.on('SIGTERM', () => stop())
  console.log(`Frontend: ${frontendUrl} | API docs: ${backendUrl}/docs`)
} catch (error) {
  console.error(error.message)
  stop(1)
}
