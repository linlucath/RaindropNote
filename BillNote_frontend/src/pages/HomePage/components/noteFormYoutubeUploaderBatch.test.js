import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm accepts YouTube handle URLs in manual uploader batch mode', () => {
  assert.match(source, /inferredPlatform === 'youtube'/)
  assert.match(source, /youtube\.com\/@/)
  assert.match(source, /请输入 YouTube 频道主页链接/)
})

test('NoteForm submits preview videos with the platform inferred from the video URL', () => {
  assert.match(source, /const fallbackPlatform = resolveSubmissionPlatform/)
  assert.match(source, /platform: video\.platform \|\| fallbackPlatform/)
})

test('NoteForm infers manual uploader batch platform from the URL instead of rendering a platform select', () => {
  assert.doesNotMatch(
    source,
    /uploaderBatchMode && uploaderSourceMode === 'manual' && \(\s*<FormField[\s\S]*name="platform"/
  )
  assert.match(
    source,
    /resolveSubmissionPlatform\(\{[\s\S]*source_type: sourceType,[\s\S]*uploader_source_mode: uploaderSourceMode,[\s\S]*video_url: watchedVideoUrl,[\s\S]*platform,[\s\S]*\}\)/
  )
})

test('NoteForm auto-loads manual uploader previews after the input changes', () => {
  assert.match(source, /shouldAutoLoadManualUploaderVideos/)
  assert.match(source, /lastAutoLoadedManualSignatureRef/)
  assert.match(source, /const autoLoadTimer = window\.setTimeout\(\(\) => \{[\s\S]*void loadPreviewBatchPage\(true\)/)
  assert.match(source, /window\.clearTimeout\(autoLoadTimer\)/)
})

test('NoteForm triggers manual uploader preview from Enter instead of a fetch button', () => {
  assert.match(source, /handleManualUploaderInputKeyDown/)
  assert.match(source, /event\.key !== 'Enter'/)
  assert.match(source, /void handlePreviewBatch\(\)/)
  assert.doesNotMatch(source, />\s*拉取\s*</)
})
