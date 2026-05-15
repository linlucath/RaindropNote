import test from 'node:test'
import assert from 'node:assert/strict'

import { getTaskPollingErrorResolution } from './taskPollingErrorHandling.ts'

test('requests audio transcription confirmation when the backend asks for it', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: 500,
      message: '需要确认音频转写',
      allowAudioTranscription: false,
    }),
    {
      shouldAskAudioTranscription: true,
      shouldMarkFailed: false,
    }
  )
})

test('marks the task as failed after the user rejects audio transcription confirmation', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: 500,
      message: '需要确认音频转写',
      allowAudioTranscription: false,
      audioTranscriptionConfirmed: false,
    }),
    {
      shouldAskAudioTranscription: false,
      shouldMarkFailed: true,
    }
  )
})

test('marks the task as failed for other backend business failures', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: 500,
      message: '任务失败',
      allowAudioTranscription: false,
    }),
    {
      shouldAskAudioTranscription: false,
      shouldMarkFailed: true,
    }
  )
})

test('ignores transient network polling failures', () => {
  assert.deepEqual(
    getTaskPollingErrorResolution({
      errorCode: -1,
      message: '请求失败，请检查网络连接',
      allowAudioTranscription: false,
    }),
    {
      shouldAskAudioTranscription: false,
      shouldMarkFailed: false,
    }
  )
})
