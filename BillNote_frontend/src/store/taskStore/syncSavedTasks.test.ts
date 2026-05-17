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
      mode: 'polished_transcript',
    },
  } satisfies Task

  const nextState = buildSyncedTasksState({
    savedTasks: [],
    existingTasks: [staleTask],
    currentTaskId: 'task-stale',
    selectedTaskId: 'task-stale',
  })

  assert.deepEqual(nextState.tasks, [])
  assert.equal(nextState.currentTaskId, null)
  assert.equal(nextState.selectedTaskId, null)
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
      mode: 'polished_transcript',
    },
  } satisfies Task

  const nextState = buildSyncedTasksState({
    savedTasks: [
      {
        task_id: 'task-success',
        status: 'SUCCESS',
        created_at: 1_778_730_000,
        result: {
          markdown: '# 标题\n\n## 校对文字稿\n\nsynced',
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
    selectedTaskId: 'task-success',
  })

  assert.deepEqual(
    nextState.tasks.map(task => task.id),
    ['task-success', 'task-pending']
  )
  assert.equal(nextState.currentTaskId, 'task-pending')
  assert.equal(nextState.selectedTaskId, 'task-success')
})

test('buildSyncedTasksState drops legacy note and raw transcript history returned by the backend', () => {
  const nextState = buildSyncedTasksState({
    savedTasks: [
      {
        task_id: 'task-note',
        status: 'SUCCESS',
        created_at: 1_778_730_000,
        result: {
          markdown: '# 标题\n\n## 要点总结\n\n旧笔记',
          audio_meta: {
            video_id: 'BVnote',
            platform: 'bilibili',
            title: '旧笔记',
          },
        },
      },
      {
        task_id: 'task-raw',
        status: 'SUCCESS',
        created_at: 1_778_730_001,
        result: {
          markdown: '# 标题\n\n## 简体中文文字稿\n\n未校对文字稿',
          audio_meta: {
            video_id: 'BVraw',
            platform: 'bilibili',
            title: '未校对文字稿',
          },
        },
      },
      {
        task_id: 'task-polished',
        status: 'SUCCESS',
        created_at: 1_778_730_002,
        result: {
          markdown: '# 标题\n\n## 校对文字稿\n\n保留内容',
          audio_meta: {
            video_id: 'BVpolished',
            platform: 'bilibili',
            title: '校对稿',
          },
        },
      },
    ],
    existingTasks: [],
    currentTaskId: null,
    selectedTaskId: null,
  })

  assert.deepEqual(
    nextState.tasks.map(task => task.id),
    ['task-polished']
  )
  assert.equal(nextState.tasks[0].formData.mode, 'polished_transcript')
})
