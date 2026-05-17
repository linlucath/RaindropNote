import assert from 'node:assert/strict'
import test from 'node:test'

import type { TaskStore } from './index.ts'
import { buildPersistedTaskState } from './persistTaskState.ts'

test('buildPersistedTaskState keeps only non-terminal tasks in storage', () => {
  const state = {
    currentTaskId: 'pending-1',
    selectedTaskId: 'history-1',
    tasks: [
      {
        id: 'pending-1',
        status: 'PENDING',
        markdown: '# draft',
        transcript: {
          full_text: 'hello',
          language: 'zh',
          raw: { a: 1 },
          segments: [{ start: 0, end: 1, text: 'x' }],
        },
        platform: 'bilibili',
        createdAt: '2026-05-14T00:00:00.000Z',
        audioMeta: {
          cover_url: '',
          duration: 0,
          file_path: '',
          platform: 'bilibili',
          raw_info: { huge: true },
          title: 'pending',
          video_id: 'BVpending',
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
      },
      {
        id: 'done-1',
        status: 'SUCCESS',
        markdown: '# final',
        transcript: { full_text: 'done', language: 'zh', raw: null, segments: [] },
        platform: 'bilibili',
        createdAt: '2026-05-14T00:00:00.000Z',
        audioMeta: {
          cover_url: '',
          duration: 0,
          file_path: '',
          platform: 'bilibili',
          raw_info: { huge: true },
          title: 'done',
          video_id: 'BVdone',
        },
        formData: {
          video_url: 'https://www.bilibili.com/video/BVdone',
          link: false,
          screenshot: false,
          platform: 'bilibili',
          quality: 'fast',
          model_name: '',
          provider_id: '',
          style: '',
          mode: 'polished_transcript',
        },
      },
    ],
  } as Pick<TaskStore, 'currentTaskId' | 'selectedTaskId' | 'tasks'>

  const persisted = buildPersistedTaskState(state)

  assert.equal(persisted.currentTaskId, 'pending-1')
  assert.equal(persisted.selectedTaskId, 'history-1')
  assert.deepEqual(
    persisted.tasks.map(task => task.id),
    ['pending-1']
  )
  assert.equal(persisted.tasks[0].markdown, '')
  assert.equal(persisted.tasks[0].transcript.full_text, '')
  assert.equal(persisted.tasks[0].audioMeta.raw_info, null)
})
