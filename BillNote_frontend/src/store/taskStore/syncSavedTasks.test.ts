import assert from 'node:assert/strict'
import test from 'node:test'

import type { Task } from './index.ts'
import { buildSyncedTasksState } from './syncSavedTasks.ts'

test('buildSyncedTasksState drops persisted tasks that are no longer returned by the backend', () => {
  const staleTask = {
    id: 'task-stale',
    status: 'SUCCESS',
    markdown: '# stale',
    transcript: { full_text: '', language: '', raw: null, segments: [] },
    platform: 'bilibili',
    createdAt: new Date('2026-05-14T00:00:00.000Z').toISOString(),
    audioMeta: {
      cover_url: '',
      duration: 0,
      file_path: '',
      platform: 'bilibili',
      raw_info: null,
      title: '旧记录',
      video_id: 'BVstale',
    },
    formData: {
      video_url: '',
      link: true,
      screenshot: false,
      platform: 'bilibili',
      quality: 'fast',
      model_name: '',
      provider_id: '',
      style: '',
      mode: 'note',
    },
  } satisfies Task

  const nextState = buildSyncedTasksState({
    savedTasks: [],
    existingTasks: [staleTask],
    currentTaskId: 'task-stale',
  })

  assert.deepEqual(nextState.tasks, [])
  assert.equal(nextState.currentTaskId, null)
})

test('buildSyncedTasksState keeps pending local-only tasks while still syncing saved tasks', () => {
  const pendingTask = {
    id: 'task-pending',
    status: 'PENDING',
    markdown: '',
    transcript: { full_text: '', language: '', raw: null, segments: [] },
    platform: 'bilibili',
    createdAt: new Date('2026-05-14T00:00:00.000Z').toISOString(),
    audioMeta: {
      cover_url: '',
      duration: 0,
      file_path: '',
      platform: '',
      raw_info: null,
      title: '',
      video_id: '',
    },
    formData: {
      video_url: 'https://www.bilibili.com/video/BVpending',
      link: false,
      screenshot: false,
      platform: 'bilibili',
      quality: 'fast',
      model_name: '',
      provider_id: '',
      style: '',
      mode: 'note',
    },
  } satisfies Task

  const nextState = buildSyncedTasksState({
    savedTasks: [
      {
        task_id: 'task-success',
        status: 'SUCCESS',
        created_at: 1_778_730_000,
        result: {
          markdown: '# synced',
          audio_meta: {
            video_id: 'BVsuccess',
            platform: 'bilibili',
            title: '已同步记录',
          },
        },
      },
    ],
    existingTasks: [pendingTask],
    currentTaskId: 'task-pending',
  })

  assert.deepEqual(
    nextState.tasks.map(task => task.id),
    ['task-success', 'task-pending']
  )
  assert.equal(nextState.currentTaskId, 'task-pending')
})
