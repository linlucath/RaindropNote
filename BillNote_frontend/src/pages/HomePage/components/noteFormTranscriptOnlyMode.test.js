import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')
const noteConstants = readFileSync(path.join(__dirname, '../../../constant/note.ts'), 'utf8')

test('NoteForm no longer exposes note mode or raw transcript toggle', () => {
  assert.doesNotMatch(source, /label: '笔记'/)
  assert.doesNotMatch(source, /name="polish_transcript"/)
  assert.doesNotMatch(source, /allow_audio_transcription/)
  assert.doesNotMatch(source, /无字幕时允许音频转写/)
  assert.doesNotMatch(source, /FormLabel>笔记风格</)
  assert.match(source, /文字稿/)
})

test('NoteForm no longer exposes local video as a video source', () => {
  assert.doesNotMatch(noteConstants, /value: 'local'/)
  assert.doesNotMatch(noteConstants, /本地视频/)
  assert.doesNotMatch(source, /platform === 'local'/)
  assert.doesNotMatch(source, /本地视频路径/)
  assert.doesNotMatch(source, />\s*本地视频\s*</)
  assert.doesNotMatch(source, /UploadCloud/)
  assert.doesNotMatch(source, /uploadFile/)
})
