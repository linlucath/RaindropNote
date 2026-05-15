import assert from 'node:assert/strict'
import test from 'node:test'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const markdownHeaderSource = readFileSync(path.join(__dirname, 'MarkdownHeader.tsx'), 'utf8')
const markdownViewerSource = readFileSync(path.join(__dirname, 'MarkdownViewer.tsx'), 'utf8')

test('MarkdownHeader no longer exposes AI chat or mind map actions', () => {
  assert.doesNotMatch(markdownHeaderSource, /AI 问答/)
  assert.doesNotMatch(markdownHeaderSource, /思维导图/)
  assert.doesNotMatch(markdownHeaderSource, /MessageSquare/)
  assert.doesNotMatch(markdownHeaderSource, /BrainCircuit/)
})

test('MarkdownViewer no longer references chat or mind map panels', () => {
  assert.doesNotMatch(markdownViewerSource, /ChatPanel/)
  assert.doesNotMatch(markdownViewerSource, /MarkmapEditor/)
  assert.doesNotMatch(markdownViewerSource, /showChat/)
  assert.doesNotMatch(markdownViewerSource, /viewMode === 'map'/)
  assert.doesNotMatch(markdownViewerSource, /导出思维导图/)
})

test('chat and markmap implementation files are removed', () => {
  assert.equal(existsSync(path.join(__dirname, 'ChatPanel.tsx')), false)
  assert.equal(existsSync(path.join(__dirname, 'MarkmapComponent.tsx')), false)
  assert.equal(existsSync(path.join(__dirname, '../../../services/chat.ts')), false)
  assert.equal(existsSync(path.join(__dirname, '../../../store/chatStore')), false)
})
