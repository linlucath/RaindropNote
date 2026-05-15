import type { GenerationMode, RuntimeTaskStatus } from '../../services/note.ts'

import type { Task } from './index.ts'

type SavedTaskItem = {
  task_id?: string
  status?: RuntimeTaskStatus | 'RUNNING' | 'FAILD'
  created_at?: number
  platform?: string
  result?: Record<string, unknown>
}

type BuildSyncedTasksStateArgs = {
  savedTasks: SavedTaskItem[]
  existingTasks: Task[]
  currentTaskId: string | null
}

const TERMINAL_TASK_STATUSES = new Set(['SUCCESS', 'FAILED', 'CANCELLED', 'FAILD'])

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function restoreTask(item: SavedTaskItem): Task | null {
  const result = asRecord(item?.result)
  const audioMeta = asRecord(result.audio_meta ?? result.audioMeta)
  const rawInfo = asRecord(audioMeta.raw_info)
  const platform =
    (typeof audioMeta.platform === 'string' && audioMeta.platform) || item?.platform || ''
  const videoUrl =
    (typeof rawInfo.webpage_url === 'string' && rawInfo.webpage_url) ||
    (typeof rawInfo.original_url === 'string' && rawInfo.original_url) ||
    (typeof rawInfo.url === 'string' && rawInfo.url) ||
    ''
  const markdown = typeof result.markdown === 'string' ? result.markdown : ''
  const isPolishedTranscript = markdown.includes('## 校对文字稿')
  const isTranscript = isPolishedTranscript || markdown.includes('## 简体中文文字稿')
  const mode: GenerationMode = isTranscript ? 'transcript' : 'note'

  if (!item?.task_id || !markdown) return null

  return {
    id: item.task_id,
    status: item.status || 'SUCCESS',
    markdown,
    transcript: asRecord(result.transcript).full_text ? result.transcript : {
      full_text: '',
      language: '',
      raw: null,
      segments: [],
    },
    platform,
    createdAt: item.created_at ? new Date(item.created_at * 1000).toISOString() : new Date().toISOString(),
    audioMeta: {
      cover_url: '',
      duration: 0,
      file_path: '',
      platform,
      raw_info: null,
      title: '',
      video_id: '',
      ...audioMeta,
    },
    formData: {
      video_url: videoUrl,
      link: true,
      screenshot: false,
      platform,
      quality: 'fast',
      model_name: typeof result.model_name === 'string' ? result.model_name : '',
      provider_id: '',
      style: typeof result.style === 'string' ? result.style : '',
      mode,
      polish_transcript: isPolishedTranscript,
    },
  }
}

export function buildSyncedTasksState({
  savedTasks,
  existingTasks,
  currentTaskId,
}: BuildSyncedTasksStateArgs): Pick<{ tasks: Task[]; currentTaskId: string | null }, 'tasks' | 'currentTaskId'> {
  const restoredTasks = savedTasks.map(restoreTask).filter(Boolean) as Task[]
  const restoredById = new Map(restoredTasks.map(task => [task.id, task]))

  const mergedExisting = existingTasks.flatMap(task => {
    const restored = restoredById.get(task.id)
    if (!restored) {
      return TERMINAL_TASK_STATUSES.has(task.status) ? [] : [task]
    }

    restoredById.delete(task.id)
    return [
      {
        ...task,
        ...restored,
        formData: {
          ...task.formData,
          ...restored.formData,
        },
      },
    ]
  })

  const tasks = [...restoredById.values(), ...mergedExisting]
  const nextCurrentTaskId =
    currentTaskId && tasks.some(task => task.id === currentTaskId) ? currentTaskId : null

  return {
    tasks,
    currentTaskId: nextCurrentTaskId,
  }
}
