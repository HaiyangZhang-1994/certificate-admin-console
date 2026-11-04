import path from 'node:path'
import { python, root, run } from './lib.mjs'

try {
  run(python(), ['-m', 'app.seed', ...process.argv.slice(2)], {
    env: { ...process.env, PYTHONPATH: path.join(root, 'backend') },
  })
} catch (error) {
  console.error(error.message)
  process.exitCode = 1
}
