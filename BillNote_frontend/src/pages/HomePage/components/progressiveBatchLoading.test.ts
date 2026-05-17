import test from 'node:test'
import assert from 'node:assert/strict'

import {
  shouldAutoLoadSelectedUploaderVideos,
  shouldRequestNextPage,
} from './progressiveBatchLoading.ts'

test('requests the next page when the list is close to the bottom', () => {
  assert.equal(
    shouldRequestNextPage({
      hasMore: true,
      loading: false,
      loadingMore: false,
      scrollTop: 620,
      clientHeight: 300,
      scrollHeight: 1000,
    }),
    true
  )
})

test('does not request the next page when the list is still far from the bottom', () => {
  assert.equal(
    shouldRequestNextPage({
      hasMore: true,
      loading: false,
      loadingMore: false,
      scrollTop: 200,
      clientHeight: 300,
      scrollHeight: 1000,
    }),
    false
  )
})

test('does not request the next page while a request is already in flight', () => {
  assert.equal(
    shouldRequestNextPage({
      hasMore: true,
      loading: false,
      loadingMore: true,
      scrollTop: 620,
      clientHeight: 300,
      scrollHeight: 1000,
    }),
    false
  )
})

test('auto-loads selected uploader videos in followings mode when idle', () => {
  assert.equal(
    shouldAutoLoadSelectedUploaderVideos({
      uploaderBatchMode: true,
      uploaderSourceMode: 'followings',
      selectedUploaderMid: '123',
      batchLoading: false,
      previewLoadingMore: false,
    }),
    true
  )
})

test('does not auto-load selected uploader videos while a preview request is already running', () => {
  assert.equal(
    shouldAutoLoadSelectedUploaderVideos({
      uploaderBatchMode: true,
      uploaderSourceMode: 'followings',
      selectedUploaderMid: '123',
      batchLoading: true,
      previewLoadingMore: false,
    }),
    false
  )
})
