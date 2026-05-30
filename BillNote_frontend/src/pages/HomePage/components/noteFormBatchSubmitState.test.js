import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm switches batch mode to direct row submission copy', () => {
  assert.match(source, /点击列表中的视频即可立即开始处理/)
  assert.match(source, /请直接点击上方视频开始处理/)
  assert.doesNotMatch(source, /开始批量处理/)
})

test('NoteForm only blocks single submit when the current form still targets the same generating task', () => {
  assert.match(source, /const sameTaskGenerating = generating && matchesCurrentTaskSubmission/)
})
