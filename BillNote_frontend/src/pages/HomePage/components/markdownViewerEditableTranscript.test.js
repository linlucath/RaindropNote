import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const markdownViewerSource = readFileSync(path.join(__dirname, 'MarkdownViewer.tsx'), 'utf8')
const noteServiceSource = readFileSync(path.join(__dirname, '../../../services/note.ts'), 'utf8')

test('MarkdownViewer edits only the active markdown block in the normal preview', () => {
  assert.match(markdownViewerSource, /activeBlockIndex/)
  assert.match(markdownViewerSource, /markdownBlocks/)
  assert.match(markdownViewerSource, /handleBlockBlur/)
  assert.match(markdownViewerSource, /<Textarea/)
  assert.match(markdownViewerSource, /onBlur=\{handleBlockBlur\}/)
  assert.doesNotMatch(markdownViewerSource, /编辑文字稿/)
  assert.doesNotMatch(markdownViewerSource, /保存修改/)
})

test('edited markdown is saved to the current task and backend result file', () => {
  assert.match(markdownViewerSource, /updateTaskContent/)
  assert.match(markdownViewerSource, /updateTaskMarkdown/)
  assert.match(noteServiceSource, /updateTaskMarkdown/)
  assert.match(noteServiceSource, /\/update_task_markdown/)
})

test('MarkdownViewer does not pass react-markdown list metadata to DOM list items', () => {
  assert.match(markdownViewerSource, /liProps/)
  assert.match(markdownViewerSource, /ordered/)
  assert.match(markdownViewerSource, /checked/)
  assert.match(markdownViewerSource, /index/)
  assert.match(markdownViewerSource, /<li className="my-1" \{\.\.\.liProps\}>/)
  assert.match(markdownViewerSource, /listProps/)
  assert.match(markdownViewerSource, /depth/)
  assert.match(markdownViewerSource, /<ul className="my-6 ml-6 list-disc \[&>li\]:mt-2" \{\.\.\.listProps\}>/)
  assert.match(markdownViewerSource, /<ol className="my-6 ml-6 list-decimal \[&>li\]:mt-2" \{\.\.\.listProps\}>/)
})

test('MarkdownViewer shows an open-video button for subtitle-only failures with a source URL', () => {
  assert.match(markdownViewerSource, /currentTask\?\.formData\?\.video_url/)
  assert.match(markdownViewerSource, /AUDIO_TRANSCRIPTION_REMOVED_MESSAGE/)
  assert.match(markdownViewerSource, /window\.open\(currentTask\.formData\.video_url, '_blank', 'noopener,noreferrer'\)/)
  assert.match(markdownViewerSource, />\s*打开视频\s*</)
})
