import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildPreviewStatusItems,
  resolvePreviewVideoAction,
} from './videoPreviewTasks.ts'

test('buildPreviewStatusItems matches preview videos to the newest local task by video url', () => {
  const items = buildPreviewStatusItems({
    videos: [
      { video_id: 'video-1', video_url: ' https://example.com/1 ', title: 'One' },
      { video_id: 'video-2', video_url: 'https://example.com/2', title: 'Two' },
    ],
    tasks: [
      {
        id: 'task-success',
        status: 'SUCCESS',
        formData: { video_url: 'https://example.com/1' },
      },
      {
        id: 'task-failed',
        status: 'FAILED',
        formData: { video_url: 'https://example.com/2' },
      },
    ],
  })

  assert.deepEqual(items, [
    { video_id: 'video-1', status: 'SUCCESS', task_id: 'task-success' },
    { video_id: 'video-2', status: 'FAILED', task_id: 'task-failed' },
  ])
})

test('resolvePreviewVideoAction opens active or successful tasks and resubmits failed ones', () => {
  assert.equal(resolvePreviewVideoAction(undefined), 'submit')
  assert.equal(resolvePreviewVideoAction({ video_id: 'video-1', status: 'SUCCESS' }), 'open')
  assert.equal(resolvePreviewVideoAction({ video_id: 'video-1', status: 'PENDING' }), 'open')
  assert.equal(resolvePreviewVideoAction({ video_id: 'video-1', status: 'FAILED' }), 'submit')
  assert.equal(resolvePreviewVideoAction({ video_id: 'video-1', status: 'CANCELLED' }), 'submit')
})
