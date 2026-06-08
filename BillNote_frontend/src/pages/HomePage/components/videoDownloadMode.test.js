import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const noteFormSource = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')
const noteServiceSource = readFileSync(path.join(__dirname, '../../../services/note.ts'), 'utf8')
const taskStoreSource = readFileSync(path.join(__dirname, '../../../store/taskStore/index.ts'), 'utf8')
const requestSource = readFileSync(path.join(__dirname, '../../../utils/request.ts'), 'utf8')

test('NoteForm exposes video download mode and resolution choices', () => {
  assert.match(noteFormSource, /task_mode/)
  assert.match(noteFormSource, /下载视频/)
  assert.match(noteFormSource, /video_resolution/)
  assert.match(noteFormSource, /1080P/)
  assert.match(noteFormSource, /720P/)
  assert.match(noteFormSource, /480P/)
})

test('video download mode is part of note service generation modes and payload', () => {
  assert.match(noteServiceSource, /export type GenerationMode = 'polished_transcript' \| 'video_download'/)
  assert.match(noteServiceSource, /video_resolution\?: string/)
  assert.match(noteServiceSource, /data\.mode === 'video_download'/)
  assert.match(noteServiceSource, /视频下载任务已提交！/)
})

test('NoteForm skips model requirement for video download submissions', () => {
  assert.match(noteFormSource, /taskMode === 'video_download'/)
  assert.match(noteFormSource, /resolvedMode: GenerationMode = values\.task_mode \|\| 'polished_transcript'/)
  assert.match(
    noteFormSource,
    /if \(resolvedMode !== 'video_download' && !hasValidGenerationPayloadSettings\(generationSettings\)\)/
  )
})

test('retrying a task preserves video download mode and resolution', () => {
  assert.match(taskStoreSource, /const retryMode = newFormData\.mode \|\| newFormData\.task_mode \|\| 'polished_transcript'/)
  assert.match(taskStoreSource, /mode: retryMode/)
  assert.match(taskStoreSource, /video_resolution: newFormData\.video_resolution \|\| 'best'/)
})

test('request error handling shows FastAPI detail messages instead of generic server errors', () => {
  assert.match(requestSource, /detail\?: string/)
  assert.match(requestSource, /res\.msg \|\| res\.detail \|\| '服务器错误，请稍后再试'/)
})
