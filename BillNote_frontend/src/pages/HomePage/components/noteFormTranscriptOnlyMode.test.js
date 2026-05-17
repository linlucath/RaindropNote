import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm no longer exposes note mode or raw transcript toggle', () => {
  assert.doesNotMatch(source, /label: '笔记'/)
  assert.doesNotMatch(source, /name="polish_transcript"/)
  assert.doesNotMatch(source, /FormLabel>笔记风格</)
  assert.match(source, /文字稿/)
})
