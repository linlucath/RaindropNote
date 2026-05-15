import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const videoBannerSource = readFileSync(path.join(__dirname, 'VideoBanner.tsx'), 'utf8')
const noteHistorySource = readFileSync(path.join(__dirname, 'NoteHistory.tsx'), 'utf8')

test('VideoBanner no longer proxies or renders cover images', () => {
  assert.doesNotMatch(videoBannerSource, /cover_url/)
  assert.doesNotMatch(videoBannerSource, /image_proxy/)
  assert.doesNotMatch(videoBannerSource, /<img/)
})

test('NoteHistory no longer renders cover thumbnails', () => {
  assert.doesNotMatch(noteHistorySource, /cover_url/)
  assert.doesNotMatch(noteHistorySource, /image_proxy/)
  assert.doesNotMatch(noteHistorySource, /LazyImage/)
  assert.doesNotMatch(noteHistorySource, /placeholder\.png/)
})
