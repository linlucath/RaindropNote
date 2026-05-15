type SubmissionSourceSnapshot = {
  source_type?: 'single' | 'uploader_batch'
  uploader_source_mode?: 'manual' | 'followings'
  video_url?: string
  platform?: string
}

type CurrentTaskLike = {
  formData?: SubmissionSourceSnapshot | null
} | null

const normalizeValue = (value?: string) => (value || '').trim()

export const shouldReuseTaskForSubmission = ({
  currentTaskId,
  currentTask,
  nextValues,
}: {
  currentTaskId?: string | null
  currentTask?: CurrentTaskLike
  nextValues: SubmissionSourceSnapshot
}) => {
  if (!currentTaskId || !currentTask?.formData) {
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
