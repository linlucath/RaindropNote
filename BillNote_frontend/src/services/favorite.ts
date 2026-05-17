import request from '@/utils/request'
import toast from 'react-hot-toast'

export interface FavoriteTranscriptItem {
  id: number
  source_task_id: string
  video_id?: string | null
  platform?: string | null
  title: string
  markdown: string
  transcript?: {
    full_text?: string
    language?: string
    raw?: unknown
    segments?: Array<{
      start: number
      end: number
      text: string
      speaker?: string
    }>
  } | null
  audio_meta?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

export const listFavorites = async () => {
  return (await request.get('/favorites')) as {
    favorites: FavoriteTranscriptItem[]
  }
}

export const getFavorite = async (favoriteId: number) => {
  return (await request.get(`/favorites/${favoriteId}`)) as {
    favorite: FavoriteTranscriptItem
  }
}

export const getFavoriteByTask = async (taskId: string) => {
  return (await request.get(`/favorites/by-task/${taskId}`)) as {
    favorite: FavoriteTranscriptItem | null
  }
}

export const createFavorite = async (taskId: string) => {
  const result = (await request.post('/favorites', { task_id: taskId })) as {
    favorite: FavoriteTranscriptItem
  }
  toast.success('已加入收藏')
  return result
}

export const deleteFavorite = async (favoriteId: number) => {
  const result = (await request.delete(`/favorites/${favoriteId}`)) as {
    deleted: number
  }
  toast.success('已取消收藏')
  return result
}
