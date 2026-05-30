import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { delete_task, generateNote, GenerationMode, RuntimeTaskStatus } from '@/services/note.ts'
import toast from 'react-hot-toast'
import { buildPersistedTaskState } from './persistTaskState.ts'
import { buildSyncedTasksState } from './syncSavedTasks.ts'

export type TaskStatus = RuntimeTaskStatus | 'RUNNING' | 'FAILD'

export interface AudioMeta {
  cover_url: string
  duration: number
  file_path: string
  platform: string
  raw_info: any
  title: string
  video_id: string
}

export interface Segment {
  start: number
  end: number
  text: string
}

export interface Transcript {
  full_text: string
  language: string
  raw: any
  segments: Segment[]
}
export interface Task {
  id: string
  markdown: string
  transcript: Transcript
  status: TaskStatus
  platform: string
  audioMeta: AudioMeta
  createdAt: string
  formData: {
    video_url: string
    source_type?: 'single' | 'uploader_batch' | 'dynamics'
    uploader_source_mode?: 'manual' | 'followings'
    link: undefined | boolean
    screenshot: undefined | boolean
    platform: string
    quality: string
    model_name: string
    provider_id: string
    style?: string
    extras?: string
    format?: string[]
    mode?: GenerationMode
    polish_transcript?: boolean
    batch_limit?: number
    skip_existing?: boolean
    video_understanding?: boolean
    video_interval?: number
    grid_size?: number[]
  }
}

interface TaskStore {
  tasks: Task[]
  currentTaskId: string | null
  selectedTaskId: string | null
  addPendingTask: (taskId: string, platform: string, formData?: any) => void
  updateTaskContent: (id: string, data: Partial<Omit<Task, 'id' | 'createdAt'>>) => void
  removeTask: (id: string) => void
  clearTasks: () => void
  setCurrentTask: (taskId: string | null) => void
  setSelectedTask: (taskId: string | null) => void
  getCurrentTask: () => Task | null
  getSelectedTask: () => Task | null
  retryTask: (id: string, payload?: any) => void
  syncSavedTasks: (savedTasks: any[]) => void
}

export const useTaskStore = create<TaskStore>()(
  persist(
    (set, get) => ({
      tasks: [],
      currentTaskId: null,
      selectedTaskId: null,

      addPendingTask: (taskId: string, platform: string, formData: any) =>
        set(state => ({
          tasks: [
            {
              formData: formData,
              id: taskId,
              status: 'PENDING',
              markdown: '',
              platform: platform,
              transcript: {
                full_text: '',
                language: '',
                raw: null,
                segments: [],
              },
              createdAt: new Date().toISOString(),
              audioMeta: {
                cover_url: '',
                duration: 0,
                file_path: '',
                platform: '',
                raw_info: null,
                title: '',
                video_id: '',
              },
            },
            ...state.tasks,
          ],
          currentTaskId: taskId,
          selectedTaskId: taskId,
        })),

      updateTaskContent: (id, data) =>
        set(state => ({
          tasks: state.tasks.map(task => {
            if (task.id !== id) return task

            if (task.status === 'SUCCESS' && data.status === 'SUCCESS') return task

            return { ...task, ...data }
          }),
        })),

      getCurrentTask: () => {
        const currentTaskId = get().currentTaskId
        return get().tasks.find(task => task.id === currentTaskId) || null
      },
      getSelectedTask: () => {
        const { currentTaskId, selectedTaskId, tasks } = get()
        const resolvedTaskId = selectedTaskId || currentTaskId
        return tasks.find(task => task.id === resolvedTaskId) || null
      },
      retryTask: async (id: string, payload?: any) => {
        if (!id) {
          toast.error('任务不存在')
          return
        }
        const task = get().tasks.find(task => task.id === id)
        console.log('retry', task)
        if (!task) return

        const newFormData = payload || task.formData
        await generateNote({
          ...newFormData,
          mode: 'polished_transcript',
          task_id: id,
        })

        set(state => ({
          tasks: state.tasks.map(t =>
            t.id === id
              ? {
                  ...t,
                  formData: newFormData, // ✅ 显式更新 formData
                  status: 'PENDING',
                }
              : t
          ),
        }))
      },

      syncSavedTasks: savedTasks =>
        set(state => {
          return buildSyncedTasksState({
            savedTasks,
            existingTasks: state.tasks,
            currentTaskId: state.currentTaskId,
            selectedTaskId: state.selectedTaskId,
          })
        }),

      removeTask: async id => {
        const task = get().tasks.find(t => t.id === id)

        // 更新 Zustand 状态
        try {
          set(state => ({
            tasks: state.tasks.filter(task => task.id !== id),
            currentTaskId: state.currentTaskId === id ? null : state.currentTaskId,
            selectedTaskId: state.selectedTaskId === id ? null : state.selectedTaskId,
          }))
        } catch (error) {
          console.warn('删除任务时写入本地缓存失败，将继续调用后端删除接口', error)
        }

        // 调用后端删除接口（如果找到了任务）
        if (task) {
          await delete_task({
            task_id: id,
            video_id: task.audioMeta.video_id,
            platform: task.platform,
          })
        }
      },

      clearTasks: () => set({ tasks: [], currentTaskId: null, selectedTaskId: null }),

      setCurrentTask: taskId => set({ currentTaskId: taskId }),
      setSelectedTask: taskId => set({ selectedTaskId: taskId }),
    }),
    {
      name: 'task-storage',
      partialize: state => buildPersistedTaskState(state),
    }
  )
)
