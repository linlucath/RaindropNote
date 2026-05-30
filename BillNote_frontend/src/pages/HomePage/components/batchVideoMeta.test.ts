import test from 'node:test'
import assert from 'node:assert/strict'

import { formatBatchVideoMeta } from './batchVideoMeta.ts'

test('formats uploader meta with play count', () => {
  assert.equal(
    formatBatchVideoMeta({
      video_id: 'BV1',
      video_url: 'https://www.bilibili.com/video/BV1',
      title: '视频1',
      author_name: '测试作者',
      view_count: 123456,
    }),
    '测试作者 · 播放 12.3万'
  )
})

test('formats play count without author name', () => {
  assert.equal(
    formatBatchVideoMeta({
      video_id: 'BV1',
      video_url: 'https://www.bilibili.com/video/BV1',
      title: '视频1',
      view_count: 840428,
    }),
    '播放 84.0万'
  )
})

test('falls back to author only when play count is unavailable', () => {
  assert.equal(
    formatBatchVideoMeta({
      video_id: 'BV1',
      video_url: 'https://www.bilibili.com/video/BV1',
      title: '视频1',
      author_name: '测试作者',
    }),
    '测试作者'
  )
})
