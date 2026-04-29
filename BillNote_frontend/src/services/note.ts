import request from '@/utils/request'
import toast from 'react-hot-toast'

export type GenerationMode = 'note' | 'transcript' | 'polished_transcript'

export const generateNote = async (data: {
  video_url: string
  platform: string
  quality: string
  model_name?: string
  provider_id?: string
  task_id?: string
  format: Array<string>
  style?: string
  extras?: string
  video_understand?: boolean
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
    toast.success('笔记生成任务已提交！')

    console.log('res', response)
    // 成功提示

    return response
  } catch (e: any) {
    console.error('❌ 请求出错', e)

    // 错误提示
    // toast.error('笔记生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
  }
}

export const delete_task = async ({ video_id, platform }) => {
  try {
    const data = {
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
    toast.error('笔记生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
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
}

export const previewBatchVideos = async (data: { space_url: string; limit: number }) => {
  return await request.post('/batch/preview', data)
}

export const startBatch = async (data: {
  videos: BatchVideo[]
  mode: GenerationMode
  quality: string
  skip_existing: boolean
  concurrency: number
  model_name?: string
  provider_id?: string
}) => {
  return await request.post('/batch/start', data)
}

export const getBatchStatus = async (batchId: string) => {
  return await request.get('/batch/status/' + batchId)
}
