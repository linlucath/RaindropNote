import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const configSource = readFileSync(path.join(__dirname, 'eslint.config.js'), 'utf8')

test('eslint config ignores generated tauri target assets', () => {
  assert.match(configSource, /src-tauri\/target/)
})
