/* NoteForm.tsx ---------------------------------------------------- */
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import {
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { FieldErrors, useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { Info, Loader2, Plus } from 'lucide-react'
import {
  BatchVideo,
  BilibiliDynamicPage,
  FollowingUploader,
  FollowingUploaderPage,
  TERMINAL_TASK_STATUSES,
  GenerationMode,
  UploaderVideoPage,
  generateNote,
  getBilibiliDynamics,
  getBilibiliFollowings,
  getBilibiliUploaderVideos,
  get_task_list,
  previewBatchVideos,
} from '@/services/note.ts'
import { getDownloaderCookie } from '@/services/downloader.ts'
import { useTaskStore } from '@/store/taskStore'
import { useModelStore } from '@/store/modelStore'
import { useHomePageStore } from '@/store/homePageStore'
import { createDefaultHomePageFormState } from '@/store/homePageStore/persistHomePageState.ts'
import {
  DEFAULT_GENERATION_QUALITY,
  getPreferredDefaultModelName,
  useGenerationSettingsStore,
} from '@/store/generationSettingsStore'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { Button } from '@/components/ui/button.tsx'
import BatchVideoPreview from '@/pages/HomePage/components/BatchVideoPreview.tsx'
import {
  getNextBatchPreviewState,
  getUniqueBatchVideos,
} from '@/pages/HomePage/components/batchVideoSelection.ts'
import {
  shouldAutoLoadManualUploaderVideos,
  shouldAutoLoadSelectedUploaderVideos,
} from '@/pages/HomePage/components/progressiveBatchLoading.ts'
import {
  hasValidGenerationPayloadSettings,
  inferPlatformFromVideoUrl,
  resolveSubmissionPlatform,
  shouldReuseTaskForSubmission,
} from '@/pages/HomePage/components/taskSubmission.ts'
import {
  buildPreviewStatusItems,
  resolvePreviewVideoAction,
} from '@/pages/HomePage/components/videoPreviewTasks.ts'
import FollowingUploaderPicker from '@/pages/HomePage/components/FollowingUploaderPicker.tsx'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import { Input } from '@/components/ui/input.tsx'
import { videoPlatforms } from '@/constant/note.ts'
import toast from 'react-hot-toast'

const isYoutubeUploaderUrl = (value?: string) => {
  if (!value) {
    return false
  }

  try {
    const url = new URL(value)
    return ['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(url.hostname) &&
      url.pathname.startsWith('/@')
  } catch {
    return false
  }
}

const isBilibiliUploaderUrl = (value?: string) => {
  if (!value) {
    return false
  }

  try {
    const url = new URL(value)
    return url.hostname.toLowerCase() === 'space.bilibili.com' && /^\/\d+/.test(url.pathname)
  } catch {
    return false
  }
}

const normalizeSupportedPlatform = (value?: string): string =>
  value && videoPlatforms.some(platform => platform.value === value) ? value : 'bilibili'

/* -------------------- 校验 Schema -------------------- */
const formSchema = z
  .object({
    video_url: z.string().optional(),
    source_type: z.enum(['single', 'uploader_batch', 'dynamics']).default('single'),
    uploader_source_mode: z.enum(['manual', 'followings']).default('manual'),
    batch_limit: z.coerce.number().min(0).max(500).default(0).optional(),
    task_mode: z.enum(['polished_transcript', 'video_download']).default('polished_transcript'),
    video_resolution: z.enum(['best', '2160', '1080', '720', '480', '360']).default('best'),
    platform: z.string().nonempty('请选择平台'),
  })
  .superRefine(
    ({ video_url, source_type, uploader_source_mode }, ctx) => {
      if (source_type === 'uploader_batch') {
        if (uploader_source_mode === 'manual') {
          if (!video_url) {
            ctx.addIssue({ code: 'custom', message: '创作者主页链接不能为空', path: ['video_url'] })
            return
          }

          const inferredPlatform = inferPlatformFromVideoUrl(video_url)
          if (inferredPlatform === 'youtube') {
            if (!isYoutubeUploaderUrl(video_url)) {
              ctx.addIssue({
                code: 'custom',
                message: '请输入 YouTube 频道主页链接',
                path: ['video_url'],
              })
            }
          } else if (inferredPlatform === 'bilibili') {
            if (!isBilibiliUploaderUrl(video_url)) {
              ctx.addIssue({
                code: 'custom',
                message: '请输入有效的创作者主页链接',
                path: ['video_url'],
              })
            }
          } else {
            ctx.addIssue({
              code: 'custom',
              message: '请输入有效的创作者或频道主页链接',
              path: ['video_url'],
            })
          }
        }
      } else if (source_type === 'dynamics') {
        // Followed dynamics are account-backed and do not need a direct video URL input.
      } else {
        if (!video_url) {
          ctx.addIssue({ code: 'custom', message: '视频链接不能为空', path: ['video_url'] })
        } else {
          try {
            const url = new URL(video_url)
            if (!['http:', 'https:'].includes(url.protocol)) throw new Error()
          } catch {
            ctx.addIssue({ code: 'custom', message: '请输入正确的视频链接', path: ['video_url'] })
          }
        }
      }
    }
  )

export type NoteFormValues = z.infer<typeof formSchema>

const PREVIEW_PAGE_SIZE = 20
const BATCH_LIMIT_ALL = 0
const MANUAL_UPLOADER_AUTOLOAD_DELAY_MS = 600

const getDynamicRequestPageSize = ({
  batchLimit,
  loadedCount,
}: {
  batchLimit: number
  loadedCount: number
}) => {
  if (batchLimit <= 0) {
    return PREVIEW_PAGE_SIZE
  }

  return Math.max(Math.min(PREVIEW_PAGE_SIZE, batchLimit - loadedCount), 0)
}

/* -------------------- 可复用子组件 -------------------- */
const SectionHeader = ({ title, tip }: { title: string; tip?: string }) => (
  <div className="mb-3 flex items-center justify-between gap-2">
    <h2 className="text-sm font-semibold text-neutral-800">{title}</h2>
    {tip && (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="hover:text-primary h-4 w-4 cursor-pointer text-neutral-400" />
          </TooltipTrigger>
          <TooltipContent className="text-xs">{tip}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )}
  </div>
)

const WorkspaceSection = ({
  title,
  tip,
  children,
  className = '',
}: {
  title: string
  tip?: string
  children: ReactNode
  className?: string
}) => (
  <section className={`rounded-md border border-neutral-200 bg-white p-4 ${className}`}>
    <SectionHeader title={title} tip={tip} />
    {children}
  </section>
)

/* -------------------- 主组件 -------------------- */
const NoteForm = () => {
  /* ---- 全局状态 ---- */
  const {
    addPendingTask,
    currentTaskId,
    setCurrentTask,
    setSelectedTask,
    getCurrentTask,
    retryTask,
    syncSavedTasks,
  } = useTaskStore()
  const tasks = useTaskStore(state => state.tasks)
  const { loadEnabledModels, modelList } = useModelStore()
  const generationModelName = useGenerationSettingsStore(state => state.model_name)
  const generationQuality = useGenerationSettingsStore(state => state.quality)
  const setGenerationSettings = useGenerationSettingsStore(state => state.setGenerationSettings)
  const initialHomePageStateRef = useRef(useHomePageStore.getState())
  const persistedFormState = initialHomePageStateRef.current.form
  const persistedPreviewState = initialHomePageStateRef.current.preview
  const setPersistedFormState = useHomePageStore(state => state.setFormState)
  const replacePersistedFormState = useHomePageStore(state => state.replaceFormState)
  const replacePersistedPreviewState = useHomePageStore(state => state.replacePreviewState)
  const clearPersistedPreviewState = useHomePageStore(state => state.clearPreviewState)
  const resetPersistedHomePageState = useHomePageStore(state => state.resetHomePageState)
  const preferredDefaultModelName = useMemo(
    () => getPreferredDefaultModelName(modelList),
    [modelList]
  )
  const resolvedModelName = generationModelName || preferredDefaultModelName
  const resolvedQuality = generationQuality || DEFAULT_GENERATION_QUALITY

  /* ---- 表单 ---- */
  const form = useForm<NoteFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      ...createDefaultHomePageFormState(),
      ...persistedFormState,
      platform: normalizeSupportedPlatform(persistedFormState.platform),
    },
  })
  const currentTask = getCurrentTask()
  const hydratedTaskIdRef = useRef<string | null>(null)
  const [previewVideos, setPreviewVideos] = useState<BatchVideo[]>(persistedPreviewState.videos)
  const [submittingPreviewVideoIds, setSubmittingPreviewVideoIds] = useState<string[]>([])
  const [batchLoading, setBatchLoading] = useState(false)
  const [previewLoadingMore, setPreviewLoadingMore] = useState(false)
  const [previewPage, setPreviewPage] = useState(persistedPreviewState.page)
  const [previewOffset, setPreviewOffset] = useState<string | null>(persistedPreviewState.offset)
  const [previewHasMore, setPreviewHasMore] = useState(persistedPreviewState.hasMore)
  const [previewSignature, setPreviewSignature] = useState<string | null>(
    persistedPreviewState.signature
  )
  const [selectedUploader, setSelectedUploader] = useState<FollowingUploader | null>(
    persistedPreviewState.selectedUploader
  )
  const [prefetchedFollowings, setPrefetchedFollowings] = useState<FollowingUploaderPage | null>(
    null
  )
  const [prefetchingFollowings, setPrefetchingFollowings] = useState(false)
  const followingsPrefetchStartedRef = useRef(false)
  const lastAutoLoadedUploaderMidRef = useRef<string | null>(null)
  const lastAutoLoadedManualSignatureRef = useRef<string | null>(null)
  const dynamicsAutoLoadStartedRef = useRef(false)

  /* ---- 派生状态（只 watch 一次，提高性能） ---- */
  const sourceType = useWatch({ control: form.control, name: 'source_type' }) as
    | 'single'
    | 'uploader_batch'
    | 'dynamics'
  const uploaderSourceMode = useWatch({ control: form.control, name: 'uploader_source_mode' }) as
    | 'manual'
    | 'followings'
  const platform = useWatch({ control: form.control, name: 'platform' }) as string
  const watchedVideoUrl = useWatch({ control: form.control, name: 'video_url' }) as
    | string
    | undefined
  const taskMode = useWatch({ control: form.control, name: 'task_mode' }) as GenerationMode
  const videoResolution = useWatch({ control: form.control, name: 'video_resolution' }) as string
  const uploaderBatchMode = sourceType === 'uploader_batch'
  const dynamicsMode = sourceType === 'dynamics'
  const batchMode = uploaderBatchMode || dynamicsMode
  const showSourceSection = !dynamicsMode
  const sourceSectionTitle = batchMode ? '1. 视频来源' : '视频来源'
  const videoSectionTitle = dynamicsMode ? '1. 选择视频' : '2. 选择视频'
  const editing = currentTask && currentTask.id
  const resolvedSourcePlatform = useMemo(
    () =>
      resolveSubmissionPlatform({
        source_type: sourceType,
        uploader_source_mode: uploaderSourceMode,
        video_url: watchedVideoUrl,
        platform,
        mode: batchMode ? 'polished_transcript' : taskMode,
        video_resolution: videoResolution,
      }),
    [batchMode, platform, sourceType, taskMode, uploaderSourceMode, videoResolution, watchedVideoUrl]
  )
  const batchRequestSignature = useMemo(
    () =>
      JSON.stringify(
        dynamicsMode
          ? { source: 'dynamics', limit: BATCH_LIMIT_ALL }
          : uploaderSourceMode === 'followings'
            ? {
                source: 'followings',
                mid: selectedUploader?.mid || '',
                limit: BATCH_LIMIT_ALL,
              }
            : {
                source: 'manual',
                platform: resolvedSourcePlatform,
                space_url: (watchedVideoUrl || '').trim(),
                limit: BATCH_LIMIT_ALL,
              }
      ),
    [
      dynamicsMode,
      resolvedSourcePlatform,
      selectedUploader?.mid,
      uploaderSourceMode,
      watchedVideoUrl,
    ]
  )
  const previewDirty =
    batchMode &&
    previewVideos.length > 0 &&
    previewSignature !== null &&
    previewSignature !== batchRequestSignature
  const previewStatusItems = useMemo(() => {
    const persistedItems = buildPreviewStatusItems({
      videos: previewVideos,
      tasks,
    })
    const existingVideoIdSet = new Set(persistedItems.map(item => item.video_id))

    const optimisticItems = submittingPreviewVideoIds
      .filter(videoId => !existingVideoIdSet.has(videoId))
      .map(videoId => ({
        video_id: videoId,
        status: 'PENDING',
      }))

    return [...persistedItems, ...optimisticItems]
  }, [previewVideos, submittingPreviewVideoIds, tasks])
  const previewStatusByVideoId = useMemo(
    () => new Map(previewStatusItems.map(item => [item.video_id, item])),
    [previewStatusItems]
  )
  const matchesCurrentTaskSubmission = shouldReuseTaskForSubmission({
    currentTaskId,
    currentTask,
    nextValues: {
      source_type: sourceType,
      uploader_source_mode: uploaderSourceMode,
      video_url: watchedVideoUrl,
      platform: resolvedSourcePlatform,
      mode: batchMode ? 'polished_transcript' : taskMode,
      video_resolution: videoResolution,
    },
    ignoreTaskStatus: true,
  })
  const resetPreviewUiState = ({
    clearSelectedUploader = true,
  }: {
    clearSelectedUploader?: boolean
  } = {}) => {
    setPreviewVideos([])
    setPreviewPage(0)
    setPreviewOffset(null)
    setPreviewHasMore(false)
    setPreviewSignature(null)
    if (clearSelectedUploader) {
      setSelectedUploader(null)
    }
    setSubmittingPreviewVideoIds([])
  }

  const getGenerationPayloadSettings = () => {
    if (!resolvedModelName) {
      return null
    }

    const selectedModel = modelList.find(model => model.model_name === resolvedModelName)
    return {
      model_name: resolvedModelName,
      quality: resolvedQuality,
      provider_id: selectedModel?.provider_id,
    }
  }

  /* ---- 副作用 ---- */
  useEffect(() => {
    loadEnabledModels()

    return
  }, [loadEnabledModels])
  useEffect(() => {
    if (
      sourceType !== 'single' &&
      !(sourceType === 'uploader_batch' && uploaderSourceMode === 'manual')
    ) {
      return
    }

    const inferredPlatform = inferPlatformFromVideoUrl(watchedVideoUrl)
    if (!inferredPlatform || inferredPlatform === platform) {
      return
    }

    form.setValue('platform', inferredPlatform, {
      shouldDirty: false,
      shouldTouch: false,
      shouldValidate: false,
    })
  }, [form, platform, sourceType, uploaderSourceMode, watchedVideoUrl])
  useEffect(() => {
    if (!preferredDefaultModelName) {
      return
    }

    if (!generationModelName) {
      setGenerationSettings({ model_name: preferredDefaultModelName })
      return
    }

    const currentModelStillExists = modelList.some(model => model.model_name === generationModelName)
    if (!currentModelStillExists) {
      setGenerationSettings({ model_name: preferredDefaultModelName })
    }
  }, [generationModelName, modelList, preferredDefaultModelName, setGenerationSettings])
  useEffect(() => {
    setPersistedFormState({
      platform: resolvedSourcePlatform || 'bilibili',
      source_type: sourceType || 'single',
      uploader_source_mode: uploaderSourceMode || 'manual',
      video_url: watchedVideoUrl || '',
      batch_limit: BATCH_LIMIT_ALL,
      task_mode: batchMode ? 'polished_transcript' : taskMode || 'polished_transcript',
      video_resolution: videoResolution || 'best',
    })
  }, [
    batchMode,
    resolvedSourcePlatform,
    setPersistedFormState,
    sourceType,
    taskMode,
    uploaderSourceMode,
    videoResolution,
    watchedVideoUrl,
  ])
  useEffect(() => {
    replacePersistedPreviewState({
      videos: previewVideos,
      page: previewPage,
      offset: previewOffset,
      hasMore: previewHasMore,
      signature: previewSignature,
      selectedUploader,
    })
  }, [
    previewHasMore,
    previewOffset,
    previewPage,
    previewSignature,
    previewVideos,
    replacePersistedPreviewState,
    selectedUploader,
  ])
  useEffect(() => {
    let cancelled = false

    if (followingsPrefetchStartedRef.current) {
      return
    }

    followingsPrefetchStartedRef.current = true

    const preloadFollowings = async () => {
      try {
        const cookieData = await getDownloaderCookie('bilibili')
        if (cancelled || !cookieData?.cookie) {
          return
        }

        setPrefetchingFollowings(true)
        const data = (await getBilibiliFollowings({
          page: 1,
          page_size: PREVIEW_PAGE_SIZE,
        })) as FollowingUploaderPage
        if (!cancelled) {
          setPrefetchedFollowings(data)
        }
      } catch {
        // Keep homepage boot quiet; the picker still allows manual refresh later.
      } finally {
        if (!cancelled) {
          setPrefetchingFollowings(false)
        }
      }
    }

    void preloadFollowings()

    return () => {
      cancelled = true
    }
  }, [])
  useEffect(() => {
    if (!currentTaskId) {
      hydratedTaskIdRef.current = null
      return
    }
    if (hydratedTaskIdRef.current === currentTaskId) return

    const task = getCurrentTask()
    if (!task) return
    const { formData } = task
    const hydratedSourceType = formData.source_type || 'single'

    // Batch item submissions should keep the current batch picker context visible instead of
    // rewriting the homepage back into a task-specific snapshot.
    if (hydratedSourceType !== 'single') {
      hydratedTaskIdRef.current = currentTaskId
      return
    }

    form.reset({
      platform: normalizeSupportedPlatform(formData.platform),
      source_type: formData.source_type || 'single',
      uploader_source_mode: formData.uploader_source_mode || 'manual',
      video_url: formData.video_url || '',
      batch_limit: BATCH_LIMIT_ALL,
      task_mode: formData.task_mode || formData.mode || 'polished_transcript',
      video_resolution: formData.video_resolution || 'best',
    })
    replacePersistedFormState({
      platform: normalizeSupportedPlatform(formData.platform),
      source_type: formData.source_type || 'single',
      uploader_source_mode: formData.uploader_source_mode || 'manual',
      video_url: formData.video_url || '',
      batch_limit: BATCH_LIMIT_ALL,
      task_mode: formData.task_mode || formData.mode || 'polished_transcript',
      video_resolution: formData.video_resolution || 'best',
    })
    resetPreviewUiState()
    clearPersistedPreviewState()
    hydratedTaskIdRef.current = currentTaskId
  }, [
    clearPersistedPreviewState,
    currentTaskId,
    form,
    getCurrentTask,
    replacePersistedFormState,
  ])
  useEffect(() => {
    if (!batchMode) {
      return
    }

    if (taskMode !== 'polished_transcript') {
      form.setValue('task_mode', 'polished_transcript', {
        shouldDirty: false,
        shouldTouch: false,
        shouldValidate: false,
      })
    }

    if (videoResolution !== 'best') {
      form.setValue('video_resolution', 'best', {
        shouldDirty: false,
        shouldTouch: false,
        shouldValidate: false,
      })
    }
  }, [batchMode, form, taskMode, videoResolution])

  const loadPreviewBatchPage = useEffectEvent(async (reset: boolean) => {
    const values = form.getValues()
    const sourceMode = values.uploader_source_mode
    const dynamicsSource = values.source_type === 'dynamics'
    const resolvedPreviewPlatform = resolveSubmissionPlatform(values)
    const valid =
      values.source_type === 'uploader_batch' && sourceMode === 'manual'
        ? await form.trigger(['video_url'])
        : true
    if (!valid) {
      toast.error('请先填写有效的创作者或频道主页链接')
      return
    }
    if (!dynamicsSource && sourceMode === 'followings' && !selectedUploader) {
      toast.error('请先从关注列表中选择一个创作者')
      return
    }
    const effectivePageSize = dynamicsSource
      ? getDynamicRequestPageSize({
          batchLimit: BATCH_LIMIT_ALL,
          loadedCount: reset ? 0 : previewVideos.length,
        })
      : PREVIEW_PAGE_SIZE
    if (dynamicsSource && effectivePageSize <= 0) {
      setPreviewHasMore(false)
      return
    }
    const nextPage = reset ? 1 : previewPage + 1
    const setLoadingState = reset ? setBatchLoading : setPreviewLoadingMore
    setLoadingState(true)
    try {
      const uploaderFallbackPayload: UploaderVideoPage = {
        items: [],
        page: nextPage,
        page_size: PREVIEW_PAGE_SIZE,
        has_more: false,
      }
      const dynamicFallbackPayload: BilibiliDynamicPage = {
        items: [],
        offset: '',
        page_size: effectivePageSize,
        has_more: false,
      }
      const payload = dynamicsSource
        ? ((await getBilibiliDynamics({
            offset: reset ? undefined : previewOffset || undefined,
            page_size: effectivePageSize,
          })) as BilibiliDynamicPage) || dynamicFallbackPayload
        : sourceMode === 'followings'
          ? ((await getBilibiliUploaderVideos({
              mid: selectedUploader?.mid || '',
              page: nextPage,
              page_size: PREVIEW_PAGE_SIZE,
              limit: BATCH_LIMIT_ALL,
            })) as UploaderVideoPage) || uploaderFallbackPayload
          : ((await previewBatchVideos({
              space_url: values.video_url || '',
              page: nextPage,
              page_size: PREVIEW_PAGE_SIZE,
              limit: BATCH_LIMIT_ALL,
            })) as UploaderVideoPage) || uploaderFallbackPayload
      const videos = getUniqueBatchVideos(payload.items || [])
      const nextPreviewState = getNextBatchPreviewState({
        currentVideos: previewVideos,
        currentSelectedIds: [],
        incomingVideos: videos,
        reset,
      })
      setPreviewVideos(nextPreviewState.videos)
      if (dynamicsSource) {
        setPreviewOffset(payload.offset || '')
      } else {
        setPreviewPage((payload as UploaderVideoPage).page)
      }
      setPreviewHasMore(payload.has_more)

      if (reset) {
        setPreviewSignature(
          JSON.stringify(
            dynamicsSource
              ? { source: 'dynamics', limit: BATCH_LIMIT_ALL }
              : sourceMode === 'followings'
                ? {
                    source: 'followings',
                    mid: selectedUploader?.mid || '',
                    limit: BATCH_LIMIT_ALL,
                  }
                : {
                    source: 'manual',
                    platform: resolvedPreviewPlatform,
                    space_url: (values.video_url || '').trim(),
                    limit: BATCH_LIMIT_ALL,
                  }
          )
        )
        setSubmittingPreviewVideoIds([])
        if (!dynamicsSource) {
          setPreviewOffset(null)
        }
      }

      if (reset && !videos.length) {
        toast.error('没有找到可预览的视频')
      }
    } finally {
      setLoadingState(false)
    }
  })

  useEffect(() => {
    const selectedUploaderMid = selectedUploader?.mid || null
    if (selectedUploaderMid === null) {
      lastAutoLoadedUploaderMidRef.current = null
      return
    }

    if (
      !shouldAutoLoadSelectedUploaderVideos({
        uploaderBatchMode,
        uploaderSourceMode,
        selectedUploaderMid,
        batchLoading,
        previewLoadingMore,
      })
    ) {
      return
    }

    if (lastAutoLoadedUploaderMidRef.current === selectedUploaderMid) {
      return
    }

    lastAutoLoadedUploaderMidRef.current = selectedUploaderMid
    void loadPreviewBatchPage(true)
  }, [
    batchLoading,
    loadPreviewBatchPage,
    selectedUploader?.mid,
    uploaderBatchMode,
    uploaderSourceMode,
    previewLoadingMore,
  ])

  useEffect(() => {
    if (uploaderSourceMode !== 'manual') {
      lastAutoLoadedManualSignatureRef.current = null
      return
    }

    if (
      !shouldAutoLoadManualUploaderVideos({
        uploaderBatchMode,
        uploaderSourceMode,
        videoUrl: watchedVideoUrl,
        batchLoading,
        previewLoadingMore,
        batchRequestSignature,
        previewSignature,
        lastAutoLoadedSignature: lastAutoLoadedManualSignatureRef.current,
      })
    ) {
      return
    }

    const autoLoadTimer = window.setTimeout(() => {
      lastAutoLoadedManualSignatureRef.current = batchRequestSignature
      void loadPreviewBatchPage(true)
    }, MANUAL_UPLOADER_AUTOLOAD_DELAY_MS)

    return () => {
      window.clearTimeout(autoLoadTimer)
    }
  }, [
    batchLoading,
    batchRequestSignature,
    loadPreviewBatchPage,
    previewLoadingMore,
    previewSignature,
    uploaderBatchMode,
    uploaderSourceMode,
    watchedVideoUrl,
  ])

  useEffect(() => {
    if (!dynamicsMode) {
      dynamicsAutoLoadStartedRef.current = false
      return
    }

    if (batchLoading || previewLoadingMore || dynamicsAutoLoadStartedRef.current) {
      return
    }

    if (previewVideos.length > 0 && !previewDirty) {
      dynamicsAutoLoadStartedRef.current = true
      return
    }

    dynamicsAutoLoadStartedRef.current = true
    void loadPreviewBatchPage(true)
  }, [
    batchLoading,
    dynamicsMode,
    loadPreviewBatchPage,
    previewDirty,
    previewLoadingMore,
    previewVideos.length,
  ])

  /* ---- 帮助函数 ---- */
  const isGenerating = () => {
    const status = getCurrentTask()?.status
    return status !== undefined && !TERMINAL_TASK_STATUSES.includes(status)
  }
  const generating = isGenerating()

  const getPreviewRefreshErrorMessage = (values: NoteFormValues) =>
    values.source_type === 'dynamics'
      ? '订阅动态已变更，请等待列表刷新后再继续'
      : values.uploader_source_mode === 'followings'
        ? '已选择的创作者已变更，请等待列表刷新后再继续'
        : '创作者链接已变更，请先刷新视频列表'

  const focusTask = (taskId: string) => {
    setCurrentTask(taskId)
    setSelectedTask(taskId)
  }

  const openExistingTask = async (taskId: string) => {
    try {
      const res = await get_task_list()
      syncSavedTasks(res?.tasks || [])
    } catch (error) {
      console.warn('同步已处理文字稿失败，将尝试打开本地任务缓存', error)
    }
    focusTask(taskId)
  }

  const submitPreviewVideo = async (video: BatchVideo, retryTaskId?: string) => {
    const generationSettings = getGenerationPayloadSettings()
    if (!generationSettings) {
      toast.error('请先在全局配置中选择模型')
      return
    }

    const values = form.getValues()
    const fallbackPlatform = resolveSubmissionPlatform({
      ...values,
      source_type: 'single',
      video_url: video.video_url,
    })
    const payload = {
      ...values,
      ...generationSettings,
      batch_limit: BATCH_LIMIT_ALL,
      video_url: video.video_url,
      platform: video.platform || fallbackPlatform,
      task_mode: 'polished_transcript' as GenerationMode,
      mode: 'polished_transcript' as GenerationMode,
      video_resolution: 'best',
    }

    setSubmittingPreviewVideoIds(current =>
      current.includes(video.video_id) ? current : [...current, video.video_id]
    )

    try {
      if (retryTaskId) {
        focusTask(retryTaskId)
        await retryTask(retryTaskId, payload)
        return
      }

      const data = await generateNote(payload)
      if (data?.task_id) {
        addPendingTask(data.task_id, payload.platform, payload)
      }
    } finally {
      setSubmittingPreviewVideoIds(current =>
        current.filter(currentVideoId => currentVideoId !== video.video_id)
      )
    }
  }

  const handlePreviewVideoActivate = async (video: BatchVideo) => {
    const values = form.getValues()

    if (
      previewDirty ||
      previewSignature !== batchRequestSignature ||
      previewVideos.length === 0
    ) {
      toast.error(getPreviewRefreshErrorMessage(values))
      return
    }

    const statusItem = previewStatusByVideoId.get(video.video_id)
    const action = resolvePreviewVideoAction(statusItem)

    if (action === 'open' && statusItem?.task_id) {
      await openExistingTask(statusItem.task_id)
      return
    }

    await submitPreviewVideo(video, statusItem?.task_id || undefined)
  }

  const onSubmit = async (values: NoteFormValues) => {
    const resolvedMode: GenerationMode = values.task_mode || 'polished_transcript'
    const generationSettings = getGenerationPayloadSettings()
    if (resolvedMode !== 'video_download' && !hasValidGenerationPayloadSettings(generationSettings)) {
      toast.error('请先在全局配置中选择可用模型')
      return
    }

    const resolvedPlatform = resolveSubmissionPlatform(values)
    const resolvedValues = {
      ...values,
      platform: resolvedPlatform,
      mode: resolvedMode,
      video_resolution: values.video_resolution || 'best',
    }
    const reuseCurrentTask = shouldReuseTaskForSubmission({
      currentTaskId,
      currentTask,
      nextValues: resolvedValues,
    })

    if (batchMode) {
      return
    }

    const payload = {
      ...resolvedValues,
      ...(generationSettings || { quality: resolvedQuality }),
      batch_limit: BATCH_LIMIT_ALL,
      mode: resolvedMode,
      task_id: reuseCurrentTask ? currentTaskId || '' : undefined,
    }
    if (reuseCurrentTask) {
      retryTask(currentTaskId, payload)
      return
    }

    const data = await generateNote(payload)
    addPendingTask(data.task_id, resolvedPlatform, payload)
  }
  const onInvalid = (errors: FieldErrors<NoteFormValues>) => {
    console.warn('表单校验失败：', errors)
    // message.error('请完善所有必填项后再提交')
  }
  const handleCreateNew = () => {
    const nextFormState = createDefaultHomePageFormState()
    form.reset(nextFormState)
    resetPreviewUiState()
    resetPersistedHomePageState()
    setCurrentTask(null)
  }
  const FormButton = () => {
    const sameTaskGenerating = generating && matchesCurrentTaskSubmission
    const label =
      taskMode === 'video_download'
        ? sameTaskGenerating
          ? '当前视频下载中'
          : editing
            ? '重新下载'
            : '下载视频'
        : sameTaskGenerating
          ? '当前文字稿生成中'
          : editing
            ? '重新生成'
            : '生成文字稿'

    if (batchMode) {
      return null
    }

    return (
      <div className="flex gap-2">
        <Button
          type="submit"
          className={editing ? 'h-11 flex-1' : 'h-11 w-full'}
          disabled={sameTaskGenerating}
        >
          {sameTaskGenerating && (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          {label}
        </Button>

        {editing && (
          <Button type="button" variant="outline" className="h-11 w-32" onClick={handleCreateNew}>
            <Plus className="mr-2 h-4 w-4" />
            新建任务
          </Button>
        )}
      </div>
    )
  }

  const handlePreviewBatch = async () => {
    await loadPreviewBatchPage(true)
  }

  const handleManualUploaderInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' || event.nativeEvent.isComposing) {
      return
    }

    if (!uploaderBatchMode || uploaderSourceMode !== 'manual') {
      return
    }

    event.preventDefault()
    if (batchLoading) {
      return
    }

    void handlePreviewBatch()
  }

  /* -------------------- 渲染 -------------------- */
  return (
    <div className="h-full w-full">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit, onInvalid)} className="space-y-4 pb-4">
          <WorkspaceSection title="任务">
            <div className="space-y-3">
              <FormField
                control={form.control}
                name="source_type"
                render={({ field }) => (
                  <FormItem>
                    <Select
                      value={field.value}
                      onValueChange={value => {
                        if (editing) {
                          setCurrentTask(null)
                        }
                        field.onChange(value)
                        form.setValue('video_url', '')
                        if (value === 'uploader_batch' || value === 'dynamics') {
                          form.setValue('platform', 'bilibili')
                          form.setValue('uploader_source_mode', 'manual')
                          form.setValue('task_mode', 'polished_transcript')
                          form.setValue('video_resolution', 'best')
                        }
                        resetPreviewUiState()
                      }}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {[
                          { value: 'single', label: '单视频' },
                          { value: 'uploader_batch', label: '创作者主页' },
                          { value: 'dynamics', label: '订阅动态' },
                        ].map(option => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {!batchMode && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="task_mode"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs font-medium text-neutral-600">
                          任务模式
                        </FormLabel>
                        <Select
                          value={field.value}
                          onValueChange={value => {
                            field.onChange(value)
                            if (editing) {
                              setCurrentTask(null)
                            }
                          }}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {[
                              { value: 'polished_transcript', label: '生成文字稿' },
                              { value: 'video_download', label: '下载视频' },
                            ].map(option => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {taskMode === 'video_download' && (
                    <FormField
                      control={form.control}
                      name="video_resolution"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs font-medium text-neutral-600">
                            下载分辨率
                          </FormLabel>
                          <Select
                            value={field.value}
                            onValueChange={value => {
                              field.onChange(value)
                              if (editing) {
                                setCurrentTask(null)
                              }
                            }}
                          >
                            <FormControl>
                              <SelectTrigger className="w-full">
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {[
                                { value: 'best', label: '最佳' },
                                { value: '2160', label: '4K' },
                                { value: '1080', label: '1080P' },
                                { value: '720', label: '720P' },
                                { value: '480', label: '480P' },
                                { value: '360', label: '360P' },
                              ].map(option => (
                                <SelectItem key={option.value} value={option.value}>
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </div>
              )}
            </div>
          </WorkspaceSection>

          {showSourceSection && (
            <WorkspaceSection title={sourceSectionTitle}>
              <div className="space-y-3">
                {uploaderBatchMode ? (
                  <FormField
                    control={form.control}
                    name="uploader_source_mode"
                    render={({ field }) => (
                      <FormItem>
                        <Select
                          value={field.value}
                          onValueChange={value => {
                            field.onChange(value)
                            resetPreviewUiState({
                              clearSelectedUploader: value !== 'followings',
                            })
                          }}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {[
                              { value: 'manual', label: '手动输入主页' },
                              { value: 'followings', label: '从关注列表选择' },
                            ].map(option => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </FormItem>
                    )}
                  />
                ) : null}

                <div
                  className={
                    uploaderBatchMode && uploaderSourceMode === 'manual'
                      ? 'flex gap-2'
                      : 'flex gap-2'
                  }
                >
                  {(!batchMode || (uploaderBatchMode && uploaderSourceMode === 'manual')) && (
                    <FormField
                      control={form.control}
                      name="video_url"
                      render={({ field }) => (
                        <FormItem className="min-w-0 flex-1">
                          <Input
                            placeholder={
                              uploaderBatchMode
                                ? 'https://space.bilibili.com/123456 或 https://www.youtube.com/@channel_handle'
                                : '粘贴你有权使用的视频或音频链接'
                            }
                            {...field}
                            onChange={event => {
                              if (editing) {
                                setCurrentTask(null)
                              }
                              field.onChange(event)
                            }}
                            onKeyDown={handleManualUploaderInputKeyDown}
                          />
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </div>

                {uploaderBatchMode && uploaderSourceMode === 'followings' ? (
                  <div className="space-y-3 rounded-md border border-neutral-200 bg-neutral-50/60 p-3">
                    <FollowingUploaderPicker
                      initialPageData={prefetchedFollowings}
                      preloading={prefetchingFollowings}
                      selectedMid={selectedUploader?.mid}
                      onSelectUploader={uploader => {
                        setSelectedUploader(uploader)
                        resetPreviewUiState({
                          clearSelectedUploader: false,
                        })
                      }}
                    />
                    {selectedUploader ? (
                      <div className="flex flex-wrap items-center gap-2 rounded-md bg-white px-3 py-2 text-xs text-neutral-600">
                        <span>已选择创作者</span>
                        <span className="font-medium text-neutral-900">
                          {selectedUploader.name}
                        </span>
                        <span className="text-neutral-400">UID {selectedUploader.mid}</span>
                      </div>
                    ) : null}
                  </div>
                ) : null}

              </div>
            </WorkspaceSection>
          )}

          {batchMode && (
            <WorkspaceSection title={videoSectionTitle}>
              <div className="space-y-3">
                <BatchVideoPreview
                  videos={previewVideos}
                  statusItems={previewStatusItems}
                  loading={batchLoading}
                  loadingMore={previewLoadingMore}
                  hasMore={previewHasMore}
                  emptyMessage={
                    dynamicsMode
                      ? '暂无动态投稿'
                      : uploaderSourceMode === 'followings'
                        ? '请选择创作者'
                        : '暂无视频标题'
                  }
                  stale={previewDirty}
                  staleMessage={
                    dynamicsMode
                      ? '订阅动态条件已变更。'
                      : uploaderSourceMode === 'followings'
                        ? '所选创作者已变更。'
                        : '创作者链接已变更。'
                  }
                  onLoadMore={() => void loadPreviewBatchPage(false)}
                  onActivateVideo={video => {
                    void handlePreviewVideoActivate(video)
                  }}
                />

              </div>
            </WorkspaceSection>
          )}

          <div className="sticky bottom-0 z-10 -mx-1 bg-white/95 px-1 pt-2 pb-1 backdrop-blur">
            <FormButton />
          </div>
        </form>
      </Form>
    </div>
  )
}

export default NoteForm
