import { inferPlatformFromVideoUrl } from './taskSubmission.ts'

const DEFAULT_AUTOLOAD_THRESHOLD_PX = 160

interface ShouldRequestNextPageOptions {
  hasMore: boolean
  loading: boolean
  loadingMore: boolean
  scrollTop: number
  clientHeight: number
  scrollHeight: number
  thresholdPx?: number
}

interface ShouldAutoLoadSelectedUploaderVideosOptions {
  uploaderBatchMode: boolean
  uploaderSourceMode: 'manual' | 'followings'
  selectedUploaderMid?: string
  batchLoading: boolean
  previewLoadingMore: boolean
}

interface ShouldAutoLoadManualUploaderVideosOptions {
  uploaderBatchMode: boolean
  uploaderSourceMode: 'manual' | 'followings'
  videoUrl?: string
  batchLoading: boolean
  previewLoadingMore: boolean
  batchRequestSignature: string
  previewSignature: string | null
  lastAutoLoadedSignature: string | null
}

const isValidManualUploaderUrl = (value?: string) => {
  const trimmedValue = value?.trim()
  if (!trimmedValue) {
    return false
  }

  try {
    const url = new URL(trimmedValue)
    const inferredPlatform = inferPlatformFromVideoUrl(trimmedValue)

    if (inferredPlatform === 'youtube') {
      return ['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(url.hostname) &&
        /^\/@[^/]+/.test(url.pathname)
    }

    if (inferredPlatform === 'bilibili') {
      return url.hostname === 'space.bilibili.com' && /^\/\d+/.test(url.pathname)
    }

    return false
  } catch {
    return false
  }
}

export function shouldRequestNextPage({
  hasMore,
  loading,
  loadingMore,
  scrollTop,
  clientHeight,
  scrollHeight,
  thresholdPx = DEFAULT_AUTOLOAD_THRESHOLD_PX,
}: ShouldRequestNextPageOptions) {
  if (!hasMore || loading || loadingMore) {
    return false
  }

  return scrollHeight - (scrollTop + clientHeight) <= thresholdPx
}

export function shouldAutoLoadSelectedUploaderVideos({
  uploaderBatchMode,
  uploaderSourceMode,
  selectedUploaderMid,
  batchLoading,
  previewLoadingMore,
}: ShouldAutoLoadSelectedUploaderVideosOptions) {
  if (!uploaderBatchMode || uploaderSourceMode !== 'followings') {
    return false
  }

  if (!selectedUploaderMid || batchLoading || previewLoadingMore) {
    return false
  }

  return true
}

export function shouldAutoLoadManualUploaderVideos({
  uploaderBatchMode,
  uploaderSourceMode,
  videoUrl,
  batchLoading,
  previewLoadingMore,
  batchRequestSignature,
  previewSignature,
  lastAutoLoadedSignature,
}: ShouldAutoLoadManualUploaderVideosOptions) {
  if (!uploaderBatchMode || uploaderSourceMode !== 'manual') {
    return false
  }

  if (batchLoading || previewLoadingMore) {
    return false
  }

  if (!isValidManualUploaderUrl(videoUrl)) {
    return false
  }

  if (previewSignature === batchRequestSignature) {
    return false
  }

  return lastAutoLoadedSignature !== batchRequestSignature
}
