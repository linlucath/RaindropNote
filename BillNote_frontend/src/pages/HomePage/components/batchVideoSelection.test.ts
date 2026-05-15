import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getNextBatchPreviewState,
  getNextSelectedBatchVideoIds,
  getUniqueBatchVideos,
  shouldToggleVideoItemFromKeydown,
} from './batchVideoSelection.ts'

test('resetting preview leaves all videos unselected by default', () => {
  const nextSelectedIds = getNextSelectedBatchVideoIds({
    currentSelectedIds: ['existing-video'],
    nextVideoIds: ['video-1', 'video-2'],
    reset: true,
  })

  assert.deepEqual(nextSelectedIds, [])
})

test('loading more videos preserves current selection without auto-selecting new ones', () => {
  const nextSelectedIds = getNextSelectedBatchVideoIds({
    currentSelectedIds: ['video-1'],
    nextVideoIds: ['video-1', 'video-2', 'video-3'],
    reset: false,
  })

  assert.deepEqual(nextSelectedIds, ['video-1'])
})

test('container keydown only toggles on enter or space from the container itself', () => {
  assert.equal(
    shouldToggleVideoItemFromKeydown({
      key: 'Enter',
      targetIsCurrentTarget: true,
    }),
    true
  )
  assert.equal(
    shouldToggleVideoItemFromKeydown({
      key: ' ',
      targetIsCurrentTarget: true,
    }),
    true
  )
  assert.equal(
    shouldToggleVideoItemFromKeydown({
      key: 'Enter',
      targetIsCurrentTarget: false,
    }),
    false
  )
  assert.equal(
    shouldToggleVideoItemFromKeydown({
      key: 'Escape',
      targetIsCurrentTarget: true,
    }),
    false
  )
})

test('loading more deduplicates videos by video_id while preserving first occurrence order', () => {
  const videos = getUniqueBatchVideos([
    { video_id: 'video-1', video_url: 'https://example.com/1', title: 'One' },
    { video_id: 'video-2', video_url: 'https://example.com/2', title: 'Two' },
    { video_id: 'video-1', video_url: 'https://example.com/1b', title: 'One Duplicate' },
  ])

  assert.deepEqual(
    videos.map(video => ({
      video_id: video.video_id,
      video_url: video.video_url,
      title: video.title,
    })),
    [
      { video_id: 'video-1', video_url: 'https://example.com/1', title: 'One' },
      { video_id: 'video-2', video_url: 'https://example.com/2', title: 'Two' },
    ]
  )
})

test('building reset preview state returns incoming videos without relying on React updater ordering', () => {
  const nextState = getNextBatchPreviewState({
    currentVideos: [{ video_id: 'old', video_url: 'https://example.com/old', title: 'Old' }],
    currentSelectedIds: ['old'],
    incomingVideos: [
      { video_id: 'video-1', video_url: 'https://example.com/1', title: 'One' },
      { video_id: 'video-2', video_url: 'https://example.com/2', title: 'Two' },
    ],
    reset: true,
  })

  assert.deepEqual(
    nextState.videos.map(video => video.video_id),
    ['video-1', 'video-2']
  )
  assert.deepEqual(nextState.selectedIds, [])
})

test('building load-more preview state preserves valid selections against the merged video list', () => {
  const nextState = getNextBatchPreviewState({
    currentVideos: [
      { video_id: 'video-1', video_url: 'https://example.com/1', title: 'One' },
      { video_id: 'video-2', video_url: 'https://example.com/2', title: 'Two' },
    ],
    currentSelectedIds: ['video-2', 'missing-video'],
    incomingVideos: [
      { video_id: 'video-2', video_url: 'https://example.com/2b', title: 'Two Duplicate' },
      { video_id: 'video-3', video_url: 'https://example.com/3', title: 'Three' },
    ],
    reset: false,
  })

  assert.deepEqual(
    nextState.videos.map(video => video.video_id),
    ['video-1', 'video-2', 'video-3']
  )
  assert.deepEqual(nextState.selectedIds, ['video-2'])
})
