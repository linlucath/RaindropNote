import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm accepts YouTube handle URLs in manual uploader batch mode', () => {
  assert.match(source, /platform === 'youtube'/)
  assert.match(source, /youtube\.com\/@/)
  assert.match(source, /请输入 YouTube 频道主页链接/)
})

test('NoteForm submits preview videos with the currently selected platform', () => {
  assert.match(source, /platform: video\.platform \|\| values\.platform/)
})
