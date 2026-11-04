import { python, run } from './lib.mjs'

try {
  run(python(), process.argv.slice(2))
} catch (error) {
  console.error(error.message)
  process.exitCode = 1
}
