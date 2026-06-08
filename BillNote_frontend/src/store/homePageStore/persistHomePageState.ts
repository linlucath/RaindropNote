import type { BatchVideo, FollowingUploader, GenerationMode } from '@/services/note.ts'

export type HomePageSourceType = 'single' | 'uploader_batch' | 'dynamics'
export type HomePageUploaderSourceMode = 'manual' | 'followings'

export interface HomePageFormState {
  video_url: string
  source_type: HomePageSourceType
  uploader_source_mode: HomePageUploaderSourceMode
  batch_limit: number
  platform: string
  task_mode: GenerationMode
  video_resolution: string
}

export interface HomePagePreviewState {
  videos: BatchVideo[]
  page: number
  offset: string | null
  hasMore: boolean
  signature: string | null
  selectedUploader: FollowingUploader | null
}

export interface PersistedHomePageState {
  form: HomePageFormState
  preview: HomePagePreviewState
}

export interface PersistedHomePageStateCandidate extends PersistedHomePageState {
  transient?: {
    batchLoading?: boolean
    previewLoadingMore?: boolean
    prefetchingFollowings?: boolean
  }
}

export function createDefaultHomePageFormState(): HomePageFormState {
  return {
    platform: 'bilibili',
    source_type: 'single',
    uploader_source_mode: 'manual',
    video_url: '',
    batch_limit: 0,
    task_mode: 'polished_transcript',
    video_resolution: 'best',
  }
}

export function createEmptyHomePagePreviewState(): HomePagePreviewState {
  return {
    videos: [],
    page: 0,
    offset: null,
    hasMore: false,
    signature: null,
    selectedUploader: null,
  }
}

export function buildPersistedHomePageState(
  state: PersistedHomePageStateCandidate
): PersistedHomePageState {
  return {
    form: { ...state.form },
    preview: {
      ...state.preview,
      videos: [...state.preview.videos],
      selectedUploader: state.preview.selectedUploader
        ? { ...state.preview.selectedUploader }
        : null,
    },
  }
}
