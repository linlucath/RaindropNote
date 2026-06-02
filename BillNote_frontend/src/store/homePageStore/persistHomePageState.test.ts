import assert from 'node:assert/strict'
import test from 'node:test'

import { buildPersistedHomePageState, createDefaultHomePageFormState } from './persistHomePageState.ts'

test('buildPersistedHomePageState keeps the home page draft and preview context', () => {
  const persisted = buildPersistedHomePageState({
    form: {
      platform: 'bilibili',
      source_type: 'uploader_batch',
      uploader_source_mode: 'followings',
      video_url: 'https://space.bilibili.com/123456',
      batch_limit: 20,
    },
    preview: {
      videos: [
        {
          video_id: 'BV1xx411c7mD',
          video_url: 'https://www.bilibili.com/video/BV1xx411c7mD',
          title: '第一条视频',
        },
      ],
      page: 2,
      offset: 'next-offset',
      hasMore: true,
      signature: '{"source":"followings","mid":"42","limit":20}',
      selectedUploader: {
        mid: '42',
        name: '测试 UP 主',
        sign: 'hello world',
      },
    },
    transient: {
      batchLoading: true,
      previewLoadingMore: true,
      prefetchingFollowings: true,
    },
  })

  assert.deepEqual(persisted.form, {
    platform: 'bilibili',
    source_type: 'uploader_batch',
    uploader_source_mode: 'followings',
    video_url: 'https://space.bilibili.com/123456',
    batch_limit: 20,
  })
  assert.equal(persisted.preview.page, 2)
  assert.equal(persisted.preview.offset, 'next-offset')
  assert.equal(persisted.preview.hasMore, true)
  assert.equal(persisted.preview.signature, '{"source":"followings","mid":"42","limit":20}')
  assert.equal(persisted.preview.selectedUploader?.mid, '42')
  assert.equal(persisted.preview.videos[0]?.video_id, 'BV1xx411c7mD')
  assert.equal('transient' in persisted, false)
})

test('createDefaultHomePageFormState falls back to the default UI values', () => {
  assert.deepEqual(createDefaultHomePageFormState(), {
    platform: 'bilibili',
    source_type: 'single',
    uploader_source_mode: 'manual',
    video_url: '',
    batch_limit: 0,
  })
})
