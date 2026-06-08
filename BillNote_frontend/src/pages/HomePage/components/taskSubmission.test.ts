import test from 'node:test'
import assert from 'node:assert/strict'

import { inferPlatformFromVideoUrl, resolveSubmissionPlatform, shouldReuseTaskForSubmission } from './taskSubmission.ts'

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

test('creates a new task when the submission switches generation mode', () => {
  assert.equal(
    shouldReuseTaskForSubmission({
      currentTaskId: 'task-1',
      currentTask: {
        formData: {
          source_type: 'single',
          video_url: 'https://www.bilibili.com/video/BV1same',
          platform: 'bilibili',
          mode: 'polished_transcript',
        },
      },
      nextValues: {
        source_type: 'single',
        video_url: 'https://www.bilibili.com/video/BV1same',
        platform: 'bilibili',
        mode: 'video_download',
      },
    }),
    false
  )
})

test('creates a new task when the requested video resolution changes', () => {
  assert.equal(
    shouldReuseTaskForSubmission({
      currentTaskId: 'task-1',
      currentTask: {
        formData: {
          source_type: 'single',
          video_url: 'https://www.bilibili.com/video/BV1same',
          platform: 'bilibili',
          mode: 'video_download',
          video_resolution: '1080',
        },
      },
      nextValues: {
        source_type: 'single',
        video_url: 'https://www.bilibili.com/video/BV1same',
        platform: 'bilibili',
        mode: 'video_download',
        video_resolution: '720',
      },
    }),
    false
  )
})

test('does not reuse the current task while that same task is still generating', () => {
  assert.equal(
    shouldReuseTaskForSubmission({
      currentTaskId: 'task-1',
      currentTask: {
        status: 'PENDING',
        formData: {
          source_type: 'single',
          uploader_source_mode: 'manual',
          video_url: 'https://www.bilibili.com/video/BV1xx411c7mD',
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
    false
  )
})

test('infers the video platform from supported http links', () => {
  assert.equal(
    inferPlatformFromVideoUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
    'youtube'
  )
  assert.equal(inferPlatformFromVideoUrl('https://youtu.be/dQw4w9WgXcQ'), 'youtube')
  assert.equal(
    inferPlatformFromVideoUrl('https://www.bilibili.com/video/BV1xx411c7mD'),
    'bilibili'
  )
  assert.equal(inferPlatformFromVideoUrl('https://b23.tv/abc123'), 'bilibili')
  assert.equal(inferPlatformFromVideoUrl('https://v.douyin.com/abc123/'), 'douyin')
  assert.equal(inferPlatformFromVideoUrl('https://v.kuaishou.com/abc123'), 'kuaishou')
})

test('does not infer a platform from non-http local video paths', () => {
  assert.equal(inferPlatformFromVideoUrl('/uploads/local.mp4'), null)
  assert.equal(inferPlatformFromVideoUrl('/Users/me/video.mp4'), null)
})

test('single video submissions prefer the platform inferred from the http link', () => {
  assert.equal(
    resolveSubmissionPlatform({
      source_type: 'single',
      video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      platform: 'bilibili',
    }),
    'youtube'
  )
})

test('manual uploader batch submissions prefer the platform inferred from the homepage URL', () => {
  assert.equal(
    resolveSubmissionPlatform({
      source_type: 'uploader_batch',
      uploader_source_mode: 'manual',
      video_url: 'https://www.youtube.com/@channel_handle',
      platform: 'bilibili',
    }),
    'youtube'
  )
  assert.equal(
    resolveSubmissionPlatform({
      source_type: 'uploader_batch',
      uploader_source_mode: 'manual',
      video_url: 'https://space.bilibili.com/123456',
      platform: 'youtube',
    }),
    'bilibili'
  )
})
