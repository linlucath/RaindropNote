import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const formSource = readFileSync(path.join(__dirname, 'Form.tsx'), 'utf8')

test('downloader form uses a multiline textarea for cookie input', () => {
  assert.match(formSource, /<Textarea/)
})

test('bilibili helper copy mentions supported paste formats', () => {
  assert.match(formSource, /原始 Cookie/)
  assert.match(formSource, /Cookie:/)
  assert.match(formSource, /curl/)
})
