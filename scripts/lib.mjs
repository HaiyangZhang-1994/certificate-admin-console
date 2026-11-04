import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

export const root = fileURLToPath(new URL('../', import.meta.url))
export const venvPython = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

export function python() {
  if (existsSync(venvPython)) return venvPython
  if (process.env.PYTHON_EXECUTABLE) return process.env.PYTHON_EXECUTABLE
  throw new Error('Run npm run setup first. Set PYTHON_EXECUTABLE if python is not on PATH.')
}

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit', ...options })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`${command} failed with exit code ${result.status}`)
}

// Avoid cmd.exe quoting and execution-policy issues by calling npm's JS entrypoint.
export function npmArgs(...args) {
  if (!process.env.npm_execpath) throw new Error('Run this script through npm.')
  return [process.env.npm_execpath, ...args]
}
