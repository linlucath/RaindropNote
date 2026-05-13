import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const switchSource = readFileSync(path.join(__dirname, 'switch.tsx'), 'utf8')

test('Switch uses a stable forwarded ref implementation', () => {
  assert.match(switchSource, /React\.forwardRef/)
  assert.doesNotMatch(switchSource, /function Switch\(\{[^)]*\bref\b/)
  assert.doesNotMatch(switchSource, /@radix-ui\/react-switch/)
})
