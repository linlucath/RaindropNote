import type { BatchVideo } from '@/services/note.ts'

interface GetNextSelectedBatchVideoIdsOptions {
  currentSelectedIds: string[]
  nextVideoIds: string[]
  reset: boolean
}

interface ShouldToggleVideoItemFromKeydownOptions {
  key: string
  targetIsCurrentTarget: boolean
}

export function getNextSelectedBatchVideoIds({
  currentSelectedIds,
  nextVideoIds,
  reset,
}: GetNextSelectedBatchVideoIdsOptions) {
  if (reset) {
    return []
  }

  const nextVideoIdSet = new Set(nextVideoIds)
  return currentSelectedIds.filter(videoId => nextVideoIdSet.has(videoId))
}

export function shouldToggleVideoItemFromKeydown({
  key,
  targetIsCurrentTarget,
}: ShouldToggleVideoItemFromKeydownOptions) {
  if (!targetIsCurrentTarget) {
    return false
  }

  return key === 'Enter' || key === ' '
}

export function getUniqueBatchVideos(videos: BatchVideo[]) {
  const seen = new Set<string>()

  return videos.filter(video => {
    if (seen.has(video.video_id)) {
      return false
    }

    seen.add(video.video_id)
    return true
  })
}
