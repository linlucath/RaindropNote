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

test('bilibili form exposes a browser import button without extra description copy', () => {
  assert.match(formSource, /从浏览器获取\\(实验性功能\\)/)
  assert.doesNotMatch(formSource, /FormDescription/)
  assert.doesNotMatch(formSource, /保存时会自动提取并校验/)
})
