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
  const commands = [
    [python(), ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8000'], root],
    [process.execPath, [path.join(root, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1'], path.join(root, 'frontend')],
  ]
  for (const [command, args, cwd] of commands) {
    const child = spawn(command, args, { cwd, stdio: 'inherit' })
    children.push(child)
    child.on('error', (error) => { console.error(error.message); stop(1) })
    child.on('exit', (code) => { if (!stopping) stop(code ?? 1) })
  }
  process.on('SIGINT', () => stop())
  process.on('SIGTERM', () => stop())
  console.log('Frontend: http://127.0.0.1:5173 | API docs: http://127.0.0.1:8000/docs')
} catch (error) {
  console.error(error.message)
  stop(1)
}
