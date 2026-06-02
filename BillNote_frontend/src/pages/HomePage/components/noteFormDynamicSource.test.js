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

test('NoteForm renders task type with the shared select control', () => {
  const fieldStart = source.indexOf('name="source_type"')
  const nextSection = source.indexOf('<WorkspaceSection title={sourceSectionTitle}>', fieldStart)
  const sourceTypeField = source.slice(fieldStart, nextSection)

  assert.match(sourceTypeField, /<Select[\s\S]*value=\{field\.value\}/)
  assert.match(sourceTypeField, /<SelectTrigger className="w-full/)
  assert.match(sourceTypeField, /<SelectItem key=\{option\.value\} value=\{option\.value\}>/)
  assert.doesNotMatch(sourceTypeField, /grid grid-cols-3/)
})

test('NoteForm hides the batch limit control and requests all available videos', () => {
  assert.doesNotMatch(source, /最多视频数/)
  assert.doesNotMatch(source, /name="batch_limit"/)
  assert.match(source, /const BATCH_LIMIT_ALL = 0/)
  assert.match(source, /limit: BATCH_LIMIT_ALL/)
  assert.match(source, /batchLimit: BATCH_LIMIT_ALL/)
})

test('NoteForm keeps uploader source mode focused on uploader flows', () => {
  assert.match(source, /uploader_source_mode: z\.enum\(\['manual', 'followings'\]\)/)
  assert.doesNotMatch(source, /uploader_source_mode: z\.enum\(\['manual', 'followings', 'dynamics'\]\)/)
})

test('NoteForm renders uploader source mode with the shared select control', () => {
  const fieldStart = source.indexOf('name="uploader_source_mode"')
  const nextField = source.indexOf('name="platform"', fieldStart)
  const uploaderSourceModeField = source.slice(fieldStart, nextField)

  assert.match(uploaderSourceModeField, /<Select[\s\S]*value=\{field\.value\}/)
  assert.match(uploaderSourceModeField, /<SelectTrigger className="w-full/)
  assert.match(uploaderSourceModeField, /disabled=\{option\.value === 'followings' && platform !== 'bilibili'\}/)
  assert.doesNotMatch(uploaderSourceModeField, /grid grid-cols-2/)
  assert.doesNotMatch(uploaderSourceModeField, /<button/)
})

test('NoteForm does not render an empty source section for followed dynamics', () => {
  assert.match(source, /const showSourceSection = !dynamicsMode/)
  assert.match(source, /\{showSourceSection && \(/)
  assert.match(source, /const videoSectionTitle = dynamicsMode \? '1\. 选择视频' : '2\. 选择视频'/)
  assert.match(source, /<WorkspaceSection title=\{videoSectionTitle\}>/)
  assert.doesNotMatch(source, /dynamicsMode && batchLoading/)
})

test('NoteForm auto-loads followed dynamics without a manual fetch button', () => {
  assert.match(source, /dynamicsAutoLoadStartedRef/)
  assert.match(source, /void loadPreviewBatchPage\(true\)/)
  assert.doesNotMatch(source, />\s*拉取关注动态\s*</)
  assert.doesNotMatch(source, /先拉取关注动态/)
})

test('NoteForm omits explanatory helper copy from dynamic and following sources', () => {
  assert.doesNotMatch(source, /关注动态会自动加载/)
  assert.doesNotMatch(source, /从列表里选择投稿视频后立即开始转写/)
  assert.doesNotMatch(source, /点击后会自动加载该 UP 主的视频列表/)
  assert.doesNotMatch(source, /视频列表会自动加载/)
  assert.doesNotMatch(source, /当前列表已锁定/)
  assert.doesNotMatch(source, /点击视频即可立即开始处理文字稿/)
})
