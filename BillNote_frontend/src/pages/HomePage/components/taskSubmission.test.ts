import test from 'node:test'
import assert from 'node:assert/strict'

import { shouldReuseTaskForSubmission } from './taskSubmission.ts'

test('reuses the current task when the submission still targets the same source video', () => {
  assert.equal(
    shouldReuseTaskForSubmission({
      currentTaskId: 'task-1',
      currentTask: {
        formData: {
          source_type: 'single',
          uploader_source_mode: 'manual',
          video_url: ' https://www.bilibili.com/video/BV1xx411c7mD ',
          platform: 'bilibili',
        },
      },
      nextValues: {
        source_type: 'single',
        uploader_source_mode: 'manual',
        video_url: 'https://www.bilibili.com/video/BV1xx411c7mD',
        platform: 'bilibili',
      },
    }),
    true
  )
})

test('creates a new task when the submitted link changes', () => {
  assert.equal(
    shouldReuseTaskForSubmission({
      currentTaskId: 'task-1',
      currentTask: {
        formData: {
          source_type: 'single',
          uploader_source_mode: 'manual',
          video_url: 'https://www.bilibili.com/video/BV1old',
          platform: 'bilibili',
        },
      },
      nextValues: {
        source_type: 'single',
        uploader_source_mode: 'manual',
        video_url: 'https://www.bilibili.com/video/BV1new',
        platform: 'bilibili',
      },
    }),
    false
  )
})

test('creates a new task when the submission switches source mode', () => {
  assert.equal(
    shouldReuseTaskForSubmission({
      currentTaskId: 'task-1',
      currentTask: {
        formData: {
          source_type: 'single',
          uploader_source_mode: 'manual',
          video_url: 'https://www.bilibili.com/video/BV1same',
          platform: 'bilibili',
        },
      },
      nextValues: {
        source_type: 'uploader_batch',
        uploader_source_mode: 'followings',
        video_url: 'https://www.bilibili.com/video/BV1same',
        platform: 'bilibili',
      },
    }),
    false
  )
})
