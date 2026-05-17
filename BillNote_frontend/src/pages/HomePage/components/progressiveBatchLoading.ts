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
