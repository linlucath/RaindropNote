import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'FollowingUploaderPicker.tsx'), 'utf8')

test('FollowingUploaderPicker avoids native buttons for uploader rows', () => {
  assert.match(source, /role="button"/)
  assert.match(source, /if \(selected\) \{\s*return\s*\}/)
})

test('FollowingUploaderPicker no longer exposes uploader search controls', () => {
  assert.doesNotMatch(source, /按昵称搜索关注的 UP 主/)
  assert.doesNotMatch(source, />\s*搜索\s*</)
})

test('FollowingUploaderPicker no longer renders remote uploader avatars', () => {
  assert.doesNotMatch(source, /item\.face/)
  assert.doesNotMatch(source, /<img/)
})

test('FollowingUploaderPicker auto-loads without manual fetch or load-more buttons', () => {
  assert.doesNotMatch(source, /拉取关注列表/)
  assert.doesNotMatch(source, />\s*加载更多\s*</)
  assert.doesNotMatch(source, /handleRefresh/)
  assert.doesNotMatch(source, /继续向下滚动自动加载/)
})
