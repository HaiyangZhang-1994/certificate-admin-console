import { existsSync } from 'node:fs'
import { npmArgs, root, run, venvPython } from './lib.mjs'
import path from 'node:path'

try {
  if (!existsSync(venvPython)) {
    const basePython = process.env.PYTHON_EXECUTABLE || 'python'
    run(basePython, ['-c', 'import sys; assert (3,12) <= sys.version_info < (3,14), "Use Python 3.12 or 3.13"'])
    run(basePython, ['-m', 'venv', path.join(root, '.venv')])
  }
  run(venvPython, ['-m', 'pip', 'install', '-r', 'backend/requirements.txt'])
  run(process.execPath, npmArgs('ci'))
  console.log('Setup complete. Run npm run dev.')
} catch (error) {
  console.error(error.message)
  process.exitCode = 1
}
