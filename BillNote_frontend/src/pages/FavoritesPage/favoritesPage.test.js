import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const appSource = readFileSync(path.join(__dirname, '../../App.tsx'), 'utf8')
const layoutSource = readFileSync(path.join(__dirname, '../../layouts/HomeLayout.tsx'), 'utf8')
const headerSource = readFileSync(
  path.join(__dirname, '../HomePage/components/MarkdownHeader.tsx'),
  'utf8'
)

test('App registers the favorites route', () => {
  assert.match(appSource, /path="favorites"/)
  assert.match(appSource, /FavoritesPage/)
})

test('HomeLayout exposes a favorites entry next to task progress', () => {
  assert.match(layoutSource, /to=\{'\/favorites'\}/)
  assert.match(layoutSource, /收藏页/)
})

test('MarkdownHeader exposes a favorite toggle action', () => {
  assert.match(headerSource, /favoriteActive/)
  assert.match(headerSource, /onToggleFavorite/)
  assert.match(headerSource, /收藏/)
})
