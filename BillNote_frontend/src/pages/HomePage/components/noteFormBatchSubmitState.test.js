import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm keeps batch submit enabled when only a single transcript task is generating', () => {
  assert.match(
    source,
    /const submitDisabled = batchMode \? batchLoading \|\| batchRunning \|\| previewDirty : generating/
  )
  assert.match(source, /disabled=\{submitDisabled\}/)
})
