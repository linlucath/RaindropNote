import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm preloads the followings first page and hydrates the picker with it', () => {
  assert.match(source, /getDownloaderCookie\('bilibili'\)/)
  assert.match(source, /getBilibiliFollowings\(\{\s*page: 1,\s*page_size: PREVIEW_PAGE_SIZE,/)
  assert.match(source, /initialPageData=\{prefetchedFollowings\}/)
  assert.match(source, /preloading=\{prefetchingFollowings\}/)
})
