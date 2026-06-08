import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const pollingSource = readFileSync(path.join(__dirname, 'useTaskPolling.ts'), 'utf8')
const taskStoreSource = readFileSync(path.join(__dirname, '../store/taskStore/index.ts'), 'utf8')
const viewerSource = readFileSync(
  path.join(__dirname, '../pages/HomePage/components/MarkdownViewer.tsx'),
  'utf8'
)
const noteServiceSource = readFileSync(path.join(__dirname, '../services/note.ts'), 'utf8')

test('polling stores backend failure messages on failed tasks', () => {
  assert.match(taskStoreSource, /message\?: string/)
  assert.match(pollingSource, /message: initialResolution\.failedMessage/)
})

test('failed preview shows the stored task failure message', () => {
  assert.match(viewerSource, /currentTask\?\.message/)
  assert.match(viewerSource, /failureMessage/)
})

test('task status polling does not replace backend errors with a generic transcript toast', () => {
  assert.doesNotMatch(noteServiceSource, /文字稿生成失败，请稍后重试/)
})
