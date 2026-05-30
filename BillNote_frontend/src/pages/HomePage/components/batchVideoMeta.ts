import type { BatchVideo } from '@/services/note.ts'

const formatViewCount = (viewCount: number) => {
  if (viewCount >= 10000) {
    return `${(viewCount / 10000).toFixed(1)}万`
  }
  return `${viewCount}`
}

export const formatBatchVideoMeta = (video: BatchVideo) => {
  const parts: string[] = []
  const authorName = video.author_name?.trim()
  if (authorName) {
    parts.push(authorName)
  }

  if (typeof video.view_count === 'number' && Number.isFinite(video.view_count)) {
    parts.push(`播放 ${formatViewCount(video.view_count)}`)
  }

  return parts.join(' · ')
}
