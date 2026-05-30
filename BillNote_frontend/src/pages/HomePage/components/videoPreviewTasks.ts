export interface PreviewVideoLike {
  video_id: string
  video_url: string
}

export interface PreviewTaskLike {
  id: string
  status: string
  formData?: {
    video_url?: string
  } | null
}

export interface PreviewStatusItem {
  video_id: string
  status: string
  task_id: string
}

type PreviewVideoAction = 'open' | 'submit'

const normalizeVideoUrl = (value?: string) => (value || '').trim()

export function buildPreviewStatusItems({
  videos,
  tasks,
}: {
  videos: PreviewVideoLike[]
  tasks: PreviewTaskLike[]
}) {
  return videos.flatMap(video => {
    const matchedTask = tasks.find(
      task => normalizeVideoUrl(task.formData?.video_url) === normalizeVideoUrl(video.video_url)
    )

    if (!matchedTask) {
      return []
    }

    return [
      {
        video_id: video.video_id,
        status: matchedTask.status,
        task_id: matchedTask.id,
      },
    ]
  })
}

export function resolvePreviewVideoAction(statusItem?: { status: string } | null): PreviewVideoAction {
  if (!statusItem) {
    return 'submit'
  }

  if (statusItem.status === 'FAILED' || statusItem.status === 'CANCELLED') {
    return 'submit'
  }

  return 'open'
}
