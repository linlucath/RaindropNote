/* NoteForm.tsx ---------------------------------------------------- */
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { useEffect, useEffectEvent, useMemo, useRef, useState, type ReactNode } from 'react'
import { FieldErrors, useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { Info, Loader2, Plus, RefreshCw, UploadCloud } from 'lucide-react'
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
  previewBatchVideos,
} from '@/services/note.ts'
import { uploadFile } from '@/services/upload.ts'
import { getDownloaderCookie } from '@/services/downloader.ts'
import { useTaskStore } from '@/store/taskStore'
import { useModelStore } from '@/store/modelStore'
import { useHomePageStore } from '@/store/homePageStore'
import {
  createDefaultHomePageFormState,
  DEFAULT_HOME_PAGE_QUALITY,
} from '@/store/homePageStore/persistHomePageState.ts'
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
import { shouldAutoLoadSelectedUploaderVideos } from '@/pages/HomePage/components/progressiveBatchLoading.ts'
import { shouldReuseTaskForSubmission } from '@/pages/HomePage/components/taskSubmission.ts'
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
import { Switch } from '@/components/ui/switch.tsx'
import { videoPlatforms } from '@/constant/note.ts'
import { useNavigate } from 'react-router-dom'
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

/* -------------------- 校验 Schema -------------------- */
const formSchema = z
  .object({
    video_url: z.string().optional(),
    source_type: z.enum(['single', 'uploader_batch', 'dynamics']).default('single'),
    uploader_source_mode: z.enum(['manual', 'followings']).default('manual'),
    batch_limit: z.coerce.number().min(0).max(500).default(0).optional(),
    skip_existing: z.boolean().default(true).optional(),
    platform: z.string().nonempty('请选择平台'),
    quality: z.enum(['fast', 'medium', 'slow']),
    model_name: z.string().optional(),
  })
  .superRefine(
    ({ video_url, platform, source_type, uploader_source_mode, model_name }, ctx) => {
      if (source_type === 'uploader_batch') {
        if (uploader_source_mode === 'manual') {
          if (!video_url) {
            ctx.addIssue({ code: 'custom', message: 'UP 主主页链接不能为空', path: ['video_url'] })
          } else if (platform === 'youtube' && !isYoutubeUploaderUrl(video_url)) {
            ctx.addIssue({
              code: 'custom',
              message: '请输入 YouTube 频道主页链接',
              path: ['video_url'],
            })
          } else if (platform !== 'youtube' && !video_url.includes('space.bilibili.com')) {
            ctx.addIssue({
              code: 'custom',
              message: '请输入 B 站 UP 主主页链接',
              path: ['video_url'],
            })
          }
        }
      } else if (source_type === 'dynamics') {
        // Followed dynamics are account-backed and do not need a direct video URL input.
      } else if (platform === 'local') {
        if (!video_url) {
          ctx.addIssue({ code: 'custom', message: '本地视频路径不能为空', path: ['video_url'] })
        }
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
      if (!model_name) {
        ctx.addIssue({ code: 'custom', message: '请选择模型', path: ['model_name'] })
      }
    }
  )

export type NoteFormValues = z.infer<typeof formSchema>

const PREVIEW_PAGE_SIZE = 20

const getPreferredDefaultModelName = (
  models: Array<{ model_name: string; provider_id: string }>
) => {
  if (!models.length) {
    return ''
  }

  return (
    models.find(model => model.provider_id === 'deepseek')?.model_name ||
    models.find(model => model.model_name.toLowerCase().includes('deepseek'))?.model_name ||
    models[0]?.model_name ||
    ''
  )
}

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
  const navigate = useNavigate()
  const [isUploading, setIsUploading] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState(false)
  /* ---- 全局状态 ---- */
  const {
    addPendingTask,
    currentTaskId,
    setCurrentTask,
    setSelectedTask,
    getCurrentTask,
    retryTask,
  } = useTaskStore()
  const tasks = useTaskStore(state => state.tasks)
  const { loadEnabledModels, modelList } = useModelStore()
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

  /* ---- 表单 ---- */
  const form = useForm<NoteFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: persistedFormState,
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
  const watchedBatchLimit = useWatch({ control: form.control, name: 'batch_limit' }) as
    | number
    | undefined
  const watchedSkipExisting = useWatch({ control: form.control, name: 'skip_existing' }) as
    | boolean
    | undefined
  const watchedQuality = useWatch({ control: form.control, name: 'quality' }) as
    | 'fast'
    | 'medium'
    | 'slow'
    | undefined
  const watchedModelName = useWatch({ control: form.control, name: 'model_name' }) as
    | string
    | undefined
  const uploaderBatchMode = sourceType === 'uploader_batch'
  const dynamicsMode = sourceType === 'dynamics'
  const batchMode = uploaderBatchMode || dynamicsMode
  const editing = currentTask && currentTask.id
  const batchRequestSignature = useMemo(
    () =>
      JSON.stringify(
        dynamicsMode
          ? { source: 'dynamics', limit: watchedBatchLimit ?? 0 }
          : uploaderSourceMode === 'followings'
            ? {
                source: 'followings',
                mid: selectedUploader?.mid || '',
                limit: watchedBatchLimit ?? 0,
              }
            : {
                source: 'manual',
                platform,
                space_url: (watchedVideoUrl || '').trim(),
                limit: watchedBatchLimit ?? 0,
              }
      ),
    [dynamicsMode, platform, selectedUploader?.mid, uploaderSourceMode, watchedBatchLimit, watchedVideoUrl]
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
      platform,
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

  const goModelAdd = () => {
    navigate('/settings/model')
  }
  /* ---- 副作用 ---- */
  useEffect(() => {
    loadEnabledModels()

    return
  }, [loadEnabledModels])
  useEffect(() => {
    const currentModelName = form.getValues('model_name')
    if (!preferredDefaultModelName) {
      return
    }

    if (!currentModelName) {
      form.setValue('model_name', preferredDefaultModelName, {
        shouldDirty: false,
        shouldTouch: false,
        shouldValidate: false,
      })
      return
    }

    const currentModelStillExists = modelList.some(model => model.model_name === currentModelName)
    if (!currentModelStillExists) {
      form.setValue('model_name', preferredDefaultModelName, {
        shouldDirty: false,
        shouldTouch: false,
        shouldValidate: false,
      })
    }
  }, [form, modelList, preferredDefaultModelName])
  useEffect(() => {
    setPersistedFormState({
      platform: platform || 'bilibili',
      source_type: sourceType || 'single',
      uploader_source_mode: uploaderSourceMode || 'manual',
      video_url: watchedVideoUrl || '',
      batch_limit: watchedBatchLimit ?? 0,
      skip_existing: watchedSkipExisting ?? true,
      quality: watchedQuality || DEFAULT_HOME_PAGE_QUALITY,
      model_name: watchedModelName || '',
    })
  }, [
    platform,
    setPersistedFormState,
    sourceType,
    uploaderSourceMode,
    watchedBatchLimit,
    watchedModelName,
    watchedQuality,
    watchedSkipExisting,
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
      platform: formData.platform || 'bilibili',
      source_type: formData.source_type || 'single',
      uploader_source_mode: formData.uploader_source_mode || 'manual',
      video_url: formData.video_url || '',
      model_name: formData.model_name || preferredDefaultModelName,
      quality: formData.quality || DEFAULT_HOME_PAGE_QUALITY,
      batch_limit: formData.batch_limit ?? 0,
      skip_existing: formData.skip_existing ?? true,
    })
    replacePersistedFormState({
      platform: formData.platform || 'bilibili',
      source_type: formData.source_type || 'single',
      uploader_source_mode: formData.uploader_source_mode || 'manual',
      video_url: formData.video_url || '',
      model_name: formData.model_name || preferredDefaultModelName,
      quality: formData.quality || DEFAULT_HOME_PAGE_QUALITY,
      batch_limit: formData.batch_limit ?? 0,
      skip_existing: formData.skip_existing ?? true,
    })
    resetPreviewUiState()
    clearPersistedPreviewState()
    hydratedTaskIdRef.current = currentTaskId
  }, [
    clearPersistedPreviewState,
    currentTaskId,
    form,
    getCurrentTask,
    preferredDefaultModelName,
    replacePersistedFormState,
  ])

  const loadPreviewBatchPage = useEffectEvent(async (reset: boolean) => {
    const values = form.getValues()
    const sourceMode = values.uploader_source_mode
    const dynamicsSource = values.source_type === 'dynamics'
    const valid = await form.trigger(
      values.source_type === 'uploader_batch' && sourceMode === 'manual'
        ? ['video_url', 'batch_limit']
        : ['batch_limit']
    )
    if (!valid) {
      toast.error(
        dynamicsSource || sourceMode !== 'manual'
          ? '请先确认最多视频数'
          : values.platform === 'youtube'
            ? '请先填写有效的 YouTube 频道主页链接'
            : '请先填写有效的 UP 主主页链接'
      )
      return
    }
    if (!dynamicsSource && sourceMode === 'followings' && !selectedUploader) {
      toast.error('请先从关注列表中选择一个 UP 主')
      return
    }
    const effectivePageSize = dynamicsSource
      ? getDynamicRequestPageSize({
          batchLimit: values.batch_limit ?? 0,
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
              limit: values.batch_limit ?? 0,
            })) as UploaderVideoPage) || uploaderFallbackPayload
          : ((await previewBatchVideos({
              space_url: values.video_url || '',
              page: nextPage,
              page_size: PREVIEW_PAGE_SIZE,
              limit: values.batch_limit ?? 0,
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
      setPreviewHasMore(
        dynamicsSource
          ? payload.has_more &&
              ((values.batch_limit ?? 0) <= 0 ||
                nextPreviewState.videos.length < (values.batch_limit ?? 0))
          : payload.has_more
      )

      if (reset) {
        setPreviewSignature(
          JSON.stringify(
            dynamicsSource
              ? { source: 'dynamics', limit: values.batch_limit ?? 0 }
              : sourceMode === 'followings'
                ? {
                    source: 'followings',
                    mid: selectedUploader?.mid || '',
                    limit: values.batch_limit ?? 0,
                  }
                : {
                    source: 'manual',
                    platform: values.platform,
                    space_url: (values.video_url || '').trim(),
                    limit: values.batch_limit ?? 0,
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

  /* ---- 帮助函数 ---- */
  const isGenerating = () => {
    const status = getCurrentTask()?.status
    return status !== undefined && !TERMINAL_TASK_STATUSES.includes(status)
  }
  const generating = isGenerating()
  const handleFileUpload = async (file: File, cb: (url: string) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    setIsUploading(true)
    setUploadSuccess(false)

    try {
      const data = await uploadFile(formData)
      cb(data.url)
      setUploadSuccess(true)
    } catch (err) {
      console.error('上传失败:', err)
      // message.error('上传失败，请重试')
    } finally {
      setIsUploading(false)
    }
  }

  const getPreviewRefreshErrorMessage = (values: NoteFormValues) =>
    values.source_type === 'dynamics'
      ? '关注动态或视频数已变更，请先重新拉取视频列表'
      : values.uploader_source_mode === 'followings'
        ? '已选择的 UP 主或视频数已变更，请先重新拉取视频列表'
        : 'UP 主链接或视频数已变更，请先重新拉取视频列表'

  const focusTask = (taskId: string) => {
    setCurrentTask(taskId)
    setSelectedTask(taskId)
  }

  const submitPreviewVideo = async (video: BatchVideo, retryTaskId?: string) => {
    const valid = await form.trigger(['model_name'])
    if (!valid) {
      toast.error('请先选择模型')
      return
    }

    const values = form.getValues()
    const selectedModel = modelList.find(model => model.model_name === values.model_name)
    const payload = {
      ...values,
      video_url: video.video_url,
      platform: video.platform || values.platform,
      mode: 'polished_transcript' as GenerationMode,
      provider_id: selectedModel?.provider_id,
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
      focusTask(statusItem.task_id)
      return
    }

    await submitPreviewVideo(video, statusItem?.task_id || undefined)
  }

  const onSubmit = async (values: NoteFormValues) => {
    const selectedModel = modelList.find(m => m.model_name === values.model_name)
    const resolvedMode: GenerationMode = 'polished_transcript'
    const reuseCurrentTask = shouldReuseTaskForSubmission({
      currentTaskId,
      currentTask,
      nextValues: values,
    })

    if (batchMode) {
      toast.error('请直接点击上方视频开始处理')
      return
    }

    const payload = {
      ...values,
      mode: resolvedMode,
      provider_id: selectedModel?.provider_id,
      task_id: reuseCurrentTask ? currentTaskId || '' : undefined,
    }
    if (reuseCurrentTask) {
      retryTask(currentTaskId, payload)
      return
    }

    const data = await generateNote(payload)
    addPendingTask(data.task_id, values.platform, payload)
  }
  const onInvalid = (errors: FieldErrors<NoteFormValues>) => {
    console.warn('表单校验失败：', errors)
    // message.error('请完善所有必填项后再提交')
  }
  const handleCreateNew = () => {
    const nextFormState = createDefaultHomePageFormState(preferredDefaultModelName)
    form.reset(nextFormState)
    resetPreviewUiState()
    resetPersistedHomePageState(preferredDefaultModelName)
    setCurrentTask(null)
  }
  const FormButton = () => {
    const sameTaskGenerating = generating && matchesCurrentTaskSubmission
    const label = sameTaskGenerating ? '当前文字稿生成中' : editing ? '重新生成' : '生成文字稿'

    if (batchMode) {
      return (
        <div className="rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
          点击列表中的视频即可立即开始处理
        </div>
      )
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
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'single', label: '单视频' },
                        { value: 'uploader_batch', label: 'UP 主批量' },
                        { value: 'dynamics', label: '关注动态' },
                      ].map(option => {
                        const active = field.value === option.value
                        return (
                          <button
                            key={option.value}
                            type="button"
                            className={`h-10 rounded-md border px-3 text-sm font-medium transition-colors ${
                              active
                                ? 'border-primary bg-primary text-white'
                                : 'border-neutral-200 bg-neutral-50 text-neutral-700 hover:border-neutral-300 hover:bg-white'
                            }`}
                            onClick={() => {
                              if (editing) {
                                setCurrentTask(null)
                              }
                              field.onChange(option.value)
                              form.setValue('video_url', '')
                              if (
                                option.value === 'uploader_batch' ||
                                option.value === 'dynamics'
                              ) {
                                form.setValue('platform', 'bilibili')
                                form.setValue('uploader_source_mode', 'manual')
                              }
                              resetPreviewUiState()
                            }}
                          >
                            {option.label}
                          </button>
                        )
                      })}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </WorkspaceSection>

          <WorkspaceSection title={batchMode ? '1. 视频来源' : '视频来源'}>
            <div className="space-y-3">
              {uploaderBatchMode ? (
                <FormField
                  control={form.control}
                  name="uploader_source_mode"
                  render={({ field }) => (
                    <FormItem>
                      <div className="grid grid-cols-2 gap-2">
                        {[
                          { value: 'manual', label: '手动输入主页' },
                          { value: 'followings', label: '从关注列表选择' },
                        ].map(option => {
                          const active = field.value === option.value
                          const disabled =
                            option.value === 'followings' && platform !== 'bilibili'
                          return (
                            <button
                              key={option.value}
                              type="button"
                              disabled={disabled}
                              className={`h-9 rounded-md border px-3 text-sm transition-colors ${
                                active
                                  ? 'border-neutral-800 bg-neutral-900 text-white'
                                  : 'border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50'
                              } ${disabled ? 'cursor-not-allowed opacity-50 hover:bg-white' : ''}`}
                              onClick={() => {
                                if (disabled) {
                                  return
                                }
                                field.onChange(option.value)
                                resetPreviewUiState({
                                  clearSelectedUploader: option.value !== 'followings',
                                })
                              }}
                            >
                              {option.label}
                            </button>
                          )
                        })}
                      </div>
                    </FormItem>
                  )}
                />
              ) : null}

              <div
                className={
                  uploaderBatchMode && uploaderSourceMode === 'manual'
                    ? 'grid grid-cols-[auto_minmax(0,1fr)_auto] gap-2'
                    : 'flex gap-2'
                }
              >
                {(!batchMode || (uploaderBatchMode && uploaderSourceMode === 'manual')) && (
                  <FormField
                    control={form.control}
                    name="platform"
                    render={({ field }) => (
                      <FormItem>
                        <Select
                          value={field.value}
                          onValueChange={value => {
                            if (editing) {
                              setCurrentTask(null)
                            }
                            field.onChange(value)
                            if (uploaderBatchMode) {
                              if (value === 'youtube') {
                                form.setValue('uploader_source_mode', 'manual')
                              }
                              resetPreviewUiState({
                                clearSelectedUploader: value !== 'bilibili',
                              })
                            }
                          }}
                        >
                          <FormControl>
                            <SelectTrigger className="w-32">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {(uploaderBatchMode
                              ? videoPlatforms.filter(
                                  p => p.value === 'bilibili' || p.value === 'youtube'
                                )
                              : videoPlatforms
                            )?.map(p => (
                              <SelectItem key={p.value} value={p.value}>
                                <div className="flex items-center justify-center gap-2">
                                  <div className="h-4 w-4">{p.logo()}</div>
                                  <span>{p.label}</span>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage style={{ display: 'none' }} />
                      </FormItem>
                    )}
                  />
                )}
                {(!batchMode || (uploaderBatchMode && uploaderSourceMode === 'manual')) && (
                  <FormField
                    control={form.control}
                    name="video_url"
                    render={({ field }) => (
                      <FormItem className="min-w-0 flex-1">
                        <Input
                          placeholder={
                            uploaderBatchMode
                              ? platform === 'youtube'
                                ? 'https://www.youtube.com/@channel_handle'
                                : 'https://space.bilibili.com/123456'
                              : platform === 'local'
                                ? '请输入本地视频路径'
                                : '请输入视频网站链接'
                          }
                          {...field}
                          onChange={event => {
                            if (editing) {
                              setCurrentTask(null)
                            }
                            field.onChange(event)
                          }}
                        />
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
                {uploaderBatchMode && uploaderSourceMode === 'manual' && (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10 px-3"
                    disabled={batchLoading}
                    onClick={handlePreviewBatch}
                  >
                    {batchLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-2 h-4 w-4" />
                    )}
                    拉取
                  </Button>
                )}
              </div>

              {batchMode && (
                <div className="rounded-md bg-neutral-50 px-3 py-2">
                  <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3">
                    <FormField
                      control={form.control}
                      name="batch_limit"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs text-neutral-500">最多视频数</FormLabel>
                          <Input className="h-8" type="number" min={0} max={500} {...field} />
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="skip_existing"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs text-neutral-500">跳过已处理</FormLabel>
                          <div className="flex h-8 items-center justify-end">
                            <Switch checked={!!field.value} onCheckedChange={field.onChange} />
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
              )}

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
                      <span>已选择 UP 主</span>
                      <span className="font-medium text-neutral-900">{selectedUploader.name}</span>
                      <span className="text-neutral-400">UID {selectedUploader.mid}</span>
                      <span className="text-sky-700">点击后会自动加载该 UP 主的视频列表</span>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {dynamicsMode ? (
                <div className="space-y-3 rounded-md border border-neutral-200 bg-neutral-50/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-white px-3 py-3 text-sm text-neutral-600">
                    <span>从关注动态里选择投稿视频，点击后立即开始转写。</span>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 px-3"
                      disabled={batchLoading}
                      onClick={handlePreviewBatch}
                    >
                      {batchLoading ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      拉取关注动态
                    </Button>
                  </div>
                </div>
              ) : null}

              <FormField
                control={form.control}
                name="video_url"
                render={({ field }) => (
                  <FormItem className="flex-1">
                    {!batchMode && platform === 'local' && (
                      <div
                        className="hover:border-primary flex h-32 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-neutral-300 bg-neutral-50 text-center transition-colors"
                        onDragOver={e => {
                          e.preventDefault()
                          e.stopPropagation()
                        }}
                        onDrop={e => {
                          e.preventDefault()
                          const file = e.dataTransfer.files?.[0]
                          if (file) handleFileUpload(file, field.onChange)
                        }}
                        onClick={() => {
                          const input = document.createElement('input')
                          input.type = 'file'
                          input.accept = 'video/*'
                          input.onchange = e => {
                            const file = (e.target as HTMLInputElement).files?.[0]
                            if (file) handleFileUpload(file, field.onChange)
                          }
                          input.click()
                        }}
                      >
                        <UploadCloud className="mb-2 h-5 w-5 text-neutral-400" />
                        {isUploading ? (
                          <p className="text-sm text-blue-500">上传中，请稍候…</p>
                        ) : uploadSuccess ? (
                          <p className="text-sm text-green-600">上传成功</p>
                        ) : (
                          <p className="text-sm text-neutral-500">
                            拖拽文件到这里上传
                            <span className="mt-1 block text-xs text-neutral-400">
                              或点击选择文件
                            </span>
                          </p>
                        )}
                      </div>
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </WorkspaceSection>

          {batchMode && (
            <WorkspaceSection title="2. 选择视频" tip="点击视频即可立即开始处理文字稿">
              <div className="space-y-3">
                <BatchVideoPreview
                  videos={previewVideos}
                  statusItems={previewStatusItems}
                  loading={batchLoading}
                  loadingMore={previewLoadingMore}
                  hasMore={previewHasMore}
                  showPreviewButton={false}
                  emptyMessage={
                    dynamicsMode
                      ? '先拉取关注动态，再点击要处理的视频'
                      : uploaderSourceMode === 'followings'
                        ? '先从关注列表选择一个 UP 主，视频列表会自动加载'
                        : '粘贴 UP 主主页后拉取视频标题'
                  }
                  stale={previewDirty}
                  staleMessage={
                    dynamicsMode
                      ? '你修改了最多视频数，当前标题列表不再对应最新条件。'
                      : uploaderSourceMode === 'followings'
                        ? '你修改了所选 UP 主或最多视频数，当前标题列表不再对应最新条件。'
                        : '你修改了 UP 主链接或最多视频数，当前标题列表不再对应最新条件。'
                  }
                  onPreview={handlePreviewBatch}
                  onLoadMore={() => void loadPreviewBatchPage(false)}
                  onActivateVideo={video => {
                    void handlePreviewVideoActivate(video)
                  }}
                />

                {previewVideos.length > 0 && !previewDirty && (
                  <div className="text-xs text-neutral-500">
                    {dynamicsMode
                      ? '当前列表已锁定到这次拉取结果。修改最多视频数后，需要重新拉取再点击视频。'
                      : `当前列表已锁定到这次拉取结果。修改${
                          uploaderSourceMode === 'followings' ? '所选 UP 主' : '链接'
                        }或视频数后，需要重新拉取再点击视频。`}
                  </div>
                )}
              </div>
            </WorkspaceSection>
          )}

          <WorkspaceSection title={batchMode ? '3. 生成设置' : '生成设置'}>
            <div className="space-y-3">
              {modelList.length > 0 ? (
                <FormField
                  control={form.control}
                  name="model_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>模型</FormLabel>
                      <Select
                        onOpenChange={() => {
                          loadEnabledModels()
                        }}
                        value={field.value}
                        onValueChange={field.onChange}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full min-w-0 truncate">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {modelList.map(m => (
                            <SelectItem key={m.id} value={m.model_name}>
                              {m.model_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : (
                <Button type="button" variant="outline" className="w-full" onClick={goModelAdd}>
                  请先添加模型
                </Button>
              )}

              <FormField
                control={form.control}
                name="quality"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>处理速度</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="fast">快速</SelectItem>
                        <SelectItem value="medium">均衡</SelectItem>
                        <SelectItem value="slow">精细</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </WorkspaceSection>

          <div className="sticky bottom-0 z-10 -mx-1 bg-white/95 px-1 pt-2 pb-1 backdrop-blur">
            <FormButton />
          </div>
        </form>
      </Form>
    </div>
  )
}

export default NoteForm
