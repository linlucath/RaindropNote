type SubmissionSourceSnapshot = {
  source_type?: 'single' | 'uploader_batch' | 'dynamics'
  uploader_source_mode?: 'manual' | 'followings'
  video_url?: string
  platform?: string
}

type CurrentTaskLike = {
  status?: string | null
  formData?: SubmissionSourceSnapshot | null
} | null

const normalizeValue = (value?: string) => (value || '').trim()
const TERMINAL_TASK_STATUSES = new Set(['SUCCESS', 'FAILED', 'CANCELLED'])

export const inferPlatformFromVideoUrl = (videoUrl?: string) => {
  const value = normalizeValue(videoUrl)
  if (!value) {
    return null
  }

  let url: URL
  try {
    url = new URL(value)
  } catch {
    return null
  }

  if (!['http:', 'https:'].includes(url.protocol)) {
    return null
  }

  const host = url.hostname.toLowerCase()
  if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com')) {
    return 'youtube'
  }
  if (host === 'b23.tv' || host === 'bilibili.com' || host.endsWith('.bilibili.com')) {
    return 'bilibili'
  }
  if (host === 'douyin.com' || host.endsWith('.douyin.com')) {
    return 'douyin'
  }
  if (host === 'kuaishou.com' || host.endsWith('.kuaishou.com')) {
    return 'kuaishou'
  }

  return null
}

export const resolveSubmissionPlatform = (values: SubmissionSourceSnapshot) => {
  const sourceType = values.source_type || 'single'
  const uploaderSourceMode = values.uploader_source_mode || 'manual'

  if (
    sourceType === 'dynamics' ||
    (sourceType === 'uploader_batch' && uploaderSourceMode === 'followings')
  ) {
    return 'bilibili'
  }

  if (sourceType === 'single' || sourceType === 'uploader_batch') {
    return inferPlatformFromVideoUrl(values.video_url) || normalizeValue(values.platform)
  }

  return normalizeValue(values.platform)
}

export const shouldReuseTaskForSubmission = ({
  currentTaskId,
  currentTask,
  nextValues,
  ignoreTaskStatus = false,
}: {
  currentTaskId?: string | null
  currentTask?: CurrentTaskLike
  nextValues: SubmissionSourceSnapshot
  ignoreTaskStatus?: boolean
}) => {
  if (!currentTaskId || !currentTask?.formData) {
    return false
  }

  if (
    !ignoreTaskStatus &&
    currentTask.status &&
    !TERMINAL_TASK_STATUSES.has(currentTask.status)
  ) {
    return false
  }

  const currentValues = currentTask.formData

  return (
    (currentValues.source_type || 'single') === (nextValues.source_type || 'single') &&
    (currentValues.uploader_source_mode || 'manual') ===
      (nextValues.uploader_source_mode || 'manual') &&
    normalizeValue(currentValues.platform) === normalizeValue(nextValues.platform) &&
    normalizeValue(currentValues.video_url) === normalizeValue(nextValues.video_url)
  )
}
