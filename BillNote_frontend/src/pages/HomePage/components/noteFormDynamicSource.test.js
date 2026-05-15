import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm exposes dynamics as a top-level source type', () => {
  assert.match(source, /source_type: z\.enum\(\['single', 'uploader_batch', 'dynamics'\]\)/)
  assert.match(source, /value: 'dynamics'/)
  assert.match(source, /label: '关注动态'/)
})

test('NoteForm keeps uploader source mode focused on uploader flows', () => {
  assert.match(source, /uploader_source_mode: z\.enum\(\['manual', 'followings'\]\)/)
  assert.doesNotMatch(source, /uploader_source_mode: z\.enum\(\['manual', 'followings', 'dynamics'\]\)/)
})

test('NoteForm has dedicated fetch copy for followed dynamics', () => {
  assert.match(source, /拉取关注动态/)
  assert.match(source, /从关注动态里选择投稿视频/)
})
