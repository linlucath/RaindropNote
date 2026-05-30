import test from 'node:test'
import assert from 'node:assert/strict'

import {
  AUDIO_TRANSCRIPTION_REMOVED_MESSAGE,
  getTaskPollingErrorResolution,
} from './taskPollingErrorHandling.ts'

test('marks the task as failed when the backend reports subtitle-only restriction', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: 500,
      message: AUDIO_TRANSCRIPTION_REMOVED_MESSAGE,
    }),
    {
      shouldMarkFailed: true,
    }
  )
})

test('marks the task as failed for other backend business failures', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: 500,
      message: '任务失败',
    }),
    {
      shouldMarkFailed: true,
    }
  )
})

test('ignores transient network polling failures', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: -1,
      message: '请求失败，请检查网络连接',
    }),
    {
      shouldMarkFailed: false,
    }
  )
})
