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
