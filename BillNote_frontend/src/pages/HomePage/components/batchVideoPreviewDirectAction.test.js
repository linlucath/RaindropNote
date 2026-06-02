import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'BatchVideoPreview.tsx'), 'utf8')

test('BatchVideoPreview exposes direct action copy instead of checkbox selection controls', () => {
  assert.match(source, /立即处理/)
  assert.match(source, /查看结果/)
  assert.match(source, /重新处理/)
  assert.doesNotMatch(source, /点击视频即可开始处理/)
  assert.doesNotMatch(source, /Checkbox/)
  assert.doesNotMatch(source, /全选/)
  assert.doesNotMatch(source, /全不选/)
})
