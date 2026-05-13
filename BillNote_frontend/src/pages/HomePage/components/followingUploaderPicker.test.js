import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'FollowingUploaderPicker.tsx'), 'utf8')

test('FollowingUploaderPicker avoids native buttons for uploader rows', () => {
  assert.match(source, /role="button"/)
  assert.match(source, /if \(selected\) \{\s*return\s*\}/)
})
