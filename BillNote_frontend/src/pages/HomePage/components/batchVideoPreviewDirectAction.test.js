import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'BatchVideoPreview.tsx'), 'utf8')

test('BatchVideoPreview keeps cards clickable without repeating immediate action copy', () => {
  assert.doesNotMatch(source, /立即处理/)
  assert.match(source, /查看结果/)
  assert.match(source, /已处理/)
  assert.match(source, /重新处理/)
  assert.doesNotMatch(source, /点击视频即可开始处理/)
  assert.doesNotMatch(source, /Checkbox/)
  assert.doesNotMatch(source, /全选/)
  assert.doesNotMatch(source, /全不选/)
})

test('BatchVideoPreview relies on scroll loading instead of a load-more button', () => {
  assert.doesNotMatch(source, />\s*加载更多\s*</)
  assert.doesNotMatch(source, /继续向下滚动自动加载/)
})

test('BatchVideoPreview does not show video count badges in the selection section', () => {
  assert.doesNotMatch(source, /共\s*\{uniqueVideos\.length\}\s*条/)
  assert.doesNotMatch(source, /已去重\s*\{uniqueVideos\.length\}\s*条/)
})
