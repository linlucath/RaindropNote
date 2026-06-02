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

test('MarkdownViewer keeps empty and loading states free of explanatory helper copy', () => {
  assert.doesNotMatch(markdownViewerSource, /输入视频链接并点击/)
  assert.doesNotMatch(markdownViewerSource, /生成文字稿"按钮/)
  assert.doesNotMatch(markdownViewerSource, /支持哔哩哔哩/)
  assert.doesNotMatch(markdownViewerSource, /这可能需要几秒钟时间/)
  assert.doesNotMatch(markdownViewerSource, /取决于视频长度/)
  assert.doesNotMatch(markdownViewerSource, /这个任务已经停止/)
  assert.doesNotMatch(markdownViewerSource, /请检查后台或稍后再试/)
})

test('chat and markmap implementation files are removed', () => {
  assert.equal(existsSync(path.join(__dirname, 'ChatPanel.tsx')), false)
  assert.equal(existsSync(path.join(__dirname, 'MarkmapComponent.tsx')), false)
  assert.equal(existsSync(path.join(__dirname, '../../../services/chat.ts')), false)
  assert.equal(existsSync(path.join(__dirname, '../../../store/chatStore')), false)
})
