import request from '@/utils/request'
import toast from 'react-hot-toast'

export type GenerationMode = 'polished_transcript'
export type RuntimeTaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'
  | 'CANCELLING'
  | 'CANCELLED'
export type BatchStatus = 'PENDING' | 'RUNNING' | 'CANCELLING' | 'CANCELLED' | 'SUCCESS' | 'FAILED'
export type BatchItemStatus = RuntimeTaskStatus | 'RUNNING' | 'SKIPPED'

export interface ProgressTaskItem {
  id: string
  task_id: string
  title: string
  platform: string
  status: RuntimeTaskStatus
  message?: string
  created_at?: string
  updated_at?: string
  has_result?: boolean
}

export interface ProgressBatchItem {
  batch_id: string
  title: string
  source_label?: string
  status: BatchStatus
  completed: number
  total: number
  updated_at?: string
  created_at?: string
  current_item_title?: string | null
  current_item_index?: number | null
  cancel_requested?: boolean
  items?: Array<{
    video_id: string
    title: string
    status: BatchItemStatus
    task_id?: string | null
    message?: string
  }>
}

export interface ProgressOverview {
  summary: {
    pending: number
    running: number
    cancelling: number
    success: number
    failed: number
    cancelled: number
  }
  tasks: {
    active: ProgressTaskItem[]
    recent_terminal: ProgressTaskItem[]
  }
  batches: {
    active: ProgressBatchItem[]
    recent_terminal: ProgressBatchItem[]
  }
}

export const TERMINAL_TASK_STATUSES: RuntimeTaskStatus[] = ['SUCCESS', 'FAILED', 'CANCELLED']
export const TERMINAL_BATCH_STATUSES: BatchStatus[] = ['SUCCESS', 'FAILED', 'CANCELLED']

export const generateNote = async (data: {
  video_url: string
  platform: string
  quality: string
  link?: boolean
  screenshot?: boolean
  model_name?: string
  provider_id?: string
  task_id?: string
  format: Array<string>
  style?: string
  extras?: string
  video_understanding?: boolean
  video_interval?: number
  grid_size: Array<number>
  mode?: GenerationMode
}) => {
  try {
    console.log('generateNote', data)
    const response = await request.post('/generate_note', data)

    if (!response) {
      if (response.data.msg) {
        toast.error(response.data.msg)
      }
      return null
    }
    toast.success('文字稿生成任务已提交！')

    console.log('res', response)
    // 成功提示

    return response
  } catch (e: unknown) {
    console.error('❌ 请求出错', e)

    // 错误提示
    // toast.error('笔记生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
  }
}

export const delete_task = async ({
  task_id,
  video_id,
  platform,
}: {
  task_id?: string
  video_id?: string
  platform?: string
}) => {
  try {
    const data = {
      task_id,
      video_id,
      platform,
    }
    const res = await request.post('/delete_task', data)

    toast.success('任务已成功删除')
    return res
  } catch (e) {
    toast.error('请求异常，删除任务失败')
    console.error('❌ 删除任务失败:', e)
    throw e
  }
}

export const get_task_status = async (task_id: string) => {
  try {
    // 成功提示

    return await request.get('/task_status/' + task_id)
  } catch (e) {
    console.error('❌ 请求出错', e)

    // 错误提示
    toast.error('文字稿生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
  }
}

export const updateTaskMarkdown = async (data: { task_id: string; markdown: string }) => {
  return (await request.post('/update_task_markdown', data)) as {
    task_id: string
    result: {
      markdown: string
      [key: string]: unknown
    }
  }
}

export const get_task_list = async () => {
  try {
    return await request.get('/task_list')
  } catch (e) {
    console.error('❌ 获取历史任务失败', e)
    throw e
  }
}

export interface BatchVideo {
  video_id: string
  video_url: string
  title?: string
  platform?: string
  author_name?: string
  view_count?: number
  dynamic_id?: string
  cover?: string
}

export interface FollowingUploader {
  mid: string
  name: string
  sign: string
}

export interface FollowingUploaderPage {
  items: FollowingUploader[]
  page: number
  page_size: number
  has_more: boolean
  total: number
}

export interface UploaderVideoPage {
  items: BatchVideo[]
  page: number
  page_size: number
  has_more: boolean
  total?: number | null
}

export interface BilibiliDynamicPage {
  items: BatchVideo[]
  offset: string
  page_size: number
  has_more: boolean
}

export const previewBatchVideos = async (data: {
  space_url: string
  limit?: number
  page?: number
  page_size?: number
}) => {
  return await request.post('/batch/preview', data, { timeout: 60000 })
}

export const getBilibiliFollowings = async (params?: {
  page?: number
  page_size?: number
}) => {
  return await request.get('/bilibili/followings', { params, timeout: 15000 })
}

export const getBilibiliUploaderVideos = async (params: {
  mid: string
  limit?: number
  page?: number
  page_size?: number
}) => {
  return await request.get('/bilibili/uploader_videos', { params, timeout: 60000 })
}

export const getBilibiliDynamics = async (params?: {
  offset?: string
  page_size?: number
}) => {
  return await request.get('/bilibili/dynamics', { params, timeout: 30000 })
}

export const startBatch = async (data: {
  videos: BatchVideo[]
  mode: GenerationMode
  quality: string
  skip_existing: boolean
  concurrency: number
  link?: boolean
  screenshot?: boolean
  model_name?: string
  provider_id?: string
  format?: string[]
  style?: string
  extras?: string
  video_understanding?: boolean
  video_interval?: number
  grid_size?: number[]
}) => {
  return await request.post('/batch/start', data)
}

export const getBatchStatus = async (batchId: string) => {
  return await request.get('/batch/status/' + batchId)
}

export const cancelTask = async (taskId: string) => {
  return await request.post('/cancel_task', { task_id: taskId })
}

export const cancelBatch = async (batchId: string) => {
  return await request.post('/batch/cancel', { batch_id: batchId })
}

export const getProgressOverview = async () => {
  return (await request.get('/progress/overview')) as ProgressOverview
}
