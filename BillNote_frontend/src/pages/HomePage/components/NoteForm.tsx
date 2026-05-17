/* NoteForm.tsx ---------------------------------------------------- */
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { FieldErrors, useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import { Info, Loader2, Plus, RefreshCw, UploadCloud } from 'lucide-react'
import {
  BatchVideo,
  BilibiliDynamicPage,
  FollowingUploader,
  FollowingUploaderPage,
  TERMINAL_BATCH_STATUSES,
  TERMINAL_TASK_STATUSES,
  GenerationMode,
  UploaderVideoPage,
  generateNote,
  getBilibiliDynamics,
  getBilibiliFollowings,
  getBilibiliUploaderVideos,
  get_task_list,
  getBatchStatus,
  previewBatchVideos,
  startBatch,
} from '@/services/note.ts'
import { uploadFile } from '@/services/upload.ts'
import { getDownloaderCookie } from '@/services/downloader.ts'
import { useTaskStore } from '@/store/taskStore'
import { useModelStore } from '@/store/modelStore'
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
    allow_audio_transcription: z.boolean().default(false).optional(),
  })
  .superRefine(
    ({ video_url, platform, source_type, uploader_source_mode, model_name }, ctx) => {
      if (source_type === 'uploader_batch') {
        if (uploader_source_mode === 'manual') {
          if (!video_url) {
            ctx.addIssue({ code: 'custom', message: 'UP 主主页链接不能为空', path: ['video_url'] })
          } else if (!video_url.includes('space.bilibili.com')) {
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

interface BatchStatusItem {
  video_id: string
  status: string
  message?: string
  task_id?: string | null
}

interface BatchStatus {
  status: string
  total: number
  completed: number
  items?: BatchStatusItem[]
}

const PREVIEW_PAGE_SIZE = 20

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
    syncSavedTasks,
  } = useTaskStore()
  const { loadEnabledModels, modelList } = useModelStore()

  /* ---- 表单 ---- */
  const form = useForm<NoteFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      platform: 'bilibili',
      source_type: 'single',
      uploader_source_mode: 'manual',
      batch_limit: 0,
      skip_existing: true,
      quality: 'medium',
      model_name: modelList[0]?.model_name || '',
      allow_audio_transcription: false,
    },
  })
  const currentTask = getCurrentTask()
  const hydratedTaskIdRef = useRef<string | null>(null)
  const [previewVideos, setPreviewVideos] = useState<BatchVideo[]>([])
  const [selectedBatchVideoIds, setSelectedBatchVideoIds] = useState<string[]>([])
  const [batchId, setBatchId] = useState<string | null>(null)
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [previewLoadingMore, setPreviewLoadingMore] = useState(false)
  const [previewPage, setPreviewPage] = useState(0)
  const [previewOffset, setPreviewOffset] = useState<string | null>(null)
  const [previewHasMore, setPreviewHasMore] = useState(false)
  const [previewSignature, setPreviewSignature] = useState<string | null>(null)
  const [selectedUploader, setSelectedUploader] = useState<FollowingUploader | null>(null)
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
  const uploaderBatchMode = sourceType === 'uploader_batch'
  const dynamicsMode = sourceType === 'dynamics'
  const batchMode = uploaderBatchMode || dynamicsMode
  const editing = currentTask && currentTask.id
  const selectedPreviewVideos = useMemo(
    () => previewVideos.filter(video => selectedBatchVideoIds.includes(video.video_id)),
    [previewVideos, selectedBatchVideoIds]
  )
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
                space_url: (watchedVideoUrl || '').trim(),
                limit: watchedBatchLimit ?? 0,
              }
      ),
    [dynamicsMode, selectedUploader?.mid, uploaderSourceMode, watchedBatchLimit, watchedVideoUrl]
  )
  const previewDirty =
    batchMode &&
    previewVideos.length > 0 &&
    previewSignature !== null &&
    previewSignature !== batchRequestSignature

  const goModelAdd = () => {
    navigate('/settings/model')
  }
  /* ---- 副作用 ---- */
  useEffect(() => {
    loadEnabledModels()

    return
  }, [loadEnabledModels])
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

    form.reset({
      platform: formData.platform || 'bilibili',
      source_type: formData.source_type || 'single',
      uploader_source_mode: formData.uploader_source_mode || 'manual',
      video_url: formData.video_url || '',
      model_name: formData.model_name || modelList[0]?.model_name || '',
      quality: formData.quality || 'medium',
      batch_limit: formData.batch_limit ?? 0,
      skip_existing: formData.skip_existing ?? true,
      allow_audio_transcription: formData.allow_audio_transcription ?? false,
    })
    setPreviewVideos([])
    setSelectedBatchVideoIds([])
    setPreviewPage(0)
    setPreviewOffset(null)
    setPreviewHasMore(false)
    setPreviewSignature(null)
    setSelectedUploader(null)
    hydratedTaskIdRef.current = currentTaskId
  }, [currentTaskId, form, getCurrentTask, modelList])

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

  const onSubmit = async (values: NoteFormValues) => {
    const selectedModel = modelList.find(m => m.model_name === values.model_name)
    const resolvedMode: GenerationMode = 'polished_transcript'
    const reuseCurrentTask = shouldReuseTaskForSubmission({
      currentTaskId,
      currentTask,
      nextValues: values,
    })

    if (batchMode) {
      if (
        previewDirty ||
        previewSignature !== batchRequestSignature ||
        previewVideos.length === 0
      ) {
        toast.error(
          values.source_type === 'dynamics'
            ? '关注动态或视频数已变更，请先重新拉取视频列表'
            : values.uploader_source_mode === 'followings'
              ? '已选择的 UP 主或视频数已变更，请先重新拉取视频列表'
              : 'UP 主链接或视频数已变更，请先重新拉取视频列表'
        )
        return
      }

      setBatchLoading(true)
      try {
        const videos = previewVideos
        const selectedIds = selectedBatchVideoIds

        const videosToProcess = videos.filter(video => selectedIds.includes(video.video_id))
        if (!videosToProcess.length) {
          toast.error('请至少选择一个视频')
          setBatchLoading(false)
          return
        }

        const data = await startBatch({
          videos: videosToProcess,
          mode: resolvedMode,
          quality: values.quality,
          skip_existing: values.skip_existing ?? true,
          concurrency: 2,
          model_name: values.model_name,
          provider_id: selectedModel?.provider_id,
          allow_audio_transcription: values.allow_audio_transcription ?? false,
        })
        setBatchId(data.batch_id)
        setBatchStatus({
          status: 'PENDING',
          total: videosToProcess.length,
          completed: 0,
          items: videosToProcess.map(video => ({
            video_id: video.video_id,
            status: 'PENDING',
            message: '',
          })),
        })
      } catch (error) {
        setBatchLoading(false)
        throw error
      }
      return
    }

    const payload = {
      ...values,
      mode: resolvedMode,
      provider_id: selectedModel?.provider_id,
      task_id: reuseCurrentTask ? currentTaskId || '' : undefined,
      allow_audio_transcription: values.allow_audio_transcription ?? false,
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
    form.reset({
      platform: 'bilibili',
      source_type: 'single',
      uploader_source_mode: 'manual',
      video_url: '',
      batch_limit: 0,
      skip_existing: true,
      quality: 'medium',
      model_name: modelList[0]?.model_name || '',
      allow_audio_transcription: false,
    })
    setPreviewVideos([])
    setSelectedBatchVideoIds([])
    setPreviewPage(0)
    setPreviewOffset(null)
    setPreviewHasMore(false)
    setBatchId(null)
    setBatchStatus(null)
    setPreviewSignature(null)
    setSelectedUploader(null)
    setCurrentTask(null)
  }
  const FormButton = () => {
    const batchRunning = batchStatus && !TERMINAL_BATCH_STATUSES.includes(batchStatus.status)
    const submitDisabled = batchMode ? batchLoading || batchRunning || previewDirty : generating
    const baseLabel = batchMode ? '开始批量处理' : '生成文字稿'
    const selectedLabel =
      batchMode && selectedPreviewVideos.length
        ? `${baseLabel}（${selectedPreviewVideos.length}）`
        : baseLabel
    const label =
      generating || batchRunning
        ? '正在生成…'
        : batchMode && previewDirty
          ? '请先重新拉取'
          : editing
            ? '重新生成'
            : selectedLabel

    return (
      <div className="flex gap-2">
        <Button
          type="submit"
          className={editing ? 'h-11 flex-1' : 'h-11 w-full'}
          disabled={submitDisabled}
        >
          {(generating || batchRunning) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
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

  const loadPreviewBatchPage = async (reset: boolean) => {
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
        currentSelectedIds: selectedBatchVideoIds,
        incomingVideos: videos,
        reset,
      })
      setPreviewVideos(nextPreviewState.videos)
      setSelectedBatchVideoIds(nextPreviewState.selectedIds)
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
                    space_url: (values.video_url || '').trim(),
                    limit: values.batch_limit ?? 0,
                  }
          )
        )
        setBatchId(null)
        setBatchStatus(null)
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
  }

  const setPreviewVideoSelected = (videoId: string, checked: boolean) => {
    setSelectedBatchVideoIds(current =>
      checked
        ? Array.from(new Set([...current, videoId]))
        : current.filter(currentVideoId => currentVideoId !== videoId)
    )
  }

  const openBatchTask = async (taskId: string) => {
    try {
      const res = await get_task_list()
      syncSavedTasks(res?.tasks || [])
      setSelectedTask(taskId)
    } catch (error) {
      console.warn('同步批量任务历史失败', error)
      toast.error('结果已生成，但同步历史失败，请稍后重试')
    }
  }

  useEffect(() => {
    if (!batchId) return
    const timer = setInterval(async () => {
      const data = await getBatchStatus(batchId)
      setBatchStatus(prev => {
        const next = data as BatchStatus
        const becameTerminal =
          prev &&
          !TERMINAL_BATCH_STATUSES.includes(
            prev.status as (typeof TERMINAL_BATCH_STATUSES)[number]
          ) &&
          TERMINAL_BATCH_STATUSES.includes(next.status as (typeof TERMINAL_BATCH_STATUSES)[number])

        if (becameTerminal) {
          get_task_list()
            .then(res => syncSavedTasks(res?.tasks || []))
            .catch(error => console.warn('同步批量历史失败', error))
        }
        return next
      })
      if (
        TERMINAL_BATCH_STATUSES.includes(data.status as (typeof TERMINAL_BATCH_STATUSES)[number])
      ) {
        setBatchLoading(false)
        clearInterval(timer)
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [batchId, syncSavedTasks])

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
                              setPreviewVideos([])
                              setSelectedBatchVideoIds([])
                              setPreviewPage(0)
                              setPreviewOffset(null)
                              setPreviewHasMore(false)
                              setBatchId(null)
                              setPreviewSignature(null)
                              setBatchStatus(null)
                              setSelectedUploader(null)
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
                          return (
                            <button
                              key={option.value}
                              type="button"
                              className={`h-9 rounded-md border px-3 text-sm transition-colors ${
                                active
                                  ? 'border-neutral-800 bg-neutral-900 text-white'
                                  : 'border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50'
                              }`}
                              onClick={() => {
                                field.onChange(option.value)
                                setPreviewVideos([])
                                setSelectedBatchVideoIds([])
                                setPreviewPage(0)
                                setPreviewOffset(null)
                                setPreviewHasMore(false)
                                setPreviewSignature(null)
                                setBatchId(null)
                                setBatchStatus(null)
                                if (option.value !== 'followings') {
                                  setSelectedUploader(null)
                                }
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
                    ? 'grid grid-cols-[minmax(0,1fr)_auto] gap-2'
                    : 'flex gap-2'
                }
              >
                {!batchMode && (
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
                          }}
                        >
                          <FormControl>
                            <SelectTrigger className="w-32">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {videoPlatforms?.map(p => (
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
                              ? 'https://space.bilibili.com/123456'
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
                      setPreviewVideos([])
                      setSelectedBatchVideoIds([])
                      setPreviewPage(0)
                      setPreviewOffset(null)
                      setPreviewHasMore(false)
                      setPreviewSignature(null)
                      setBatchId(null)
                      setBatchStatus(null)
                    }}
                  />
                  {selectedUploader ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-md bg-white px-3 py-2 text-xs text-neutral-600">
                      <span>已选择 UP 主</span>
                      <span className="font-medium text-neutral-900">{selectedUploader.name}</span>
                      <span className="text-neutral-400">UID {selectedUploader.mid}</span>
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
                        拉取该 UP 主视频
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {dynamicsMode ? (
                <div className="space-y-3 rounded-md border border-neutral-200 bg-neutral-50/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-white px-3 py-3 text-sm text-neutral-600">
                    <span>从关注动态里选择投稿视频，再开始批量转写。</span>
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
            <WorkspaceSection title="2. 选择视频" tip="标题是主要信息，勾选后再开始批量处理">
              <div className="space-y-3">
                <BatchVideoPreview
                  videos={previewVideos}
                  selectedVideoIds={selectedBatchVideoIds}
                  statusItems={batchStatus?.items || []}
                  loading={batchLoading}
                  loadingMore={previewLoadingMore}
                  hasMore={previewHasMore}
                  showPreviewButton={false}
                  emptyMessage={
                    dynamicsMode
                      ? '先拉取关注动态，再从里面选择投稿视频'
                      : uploaderSourceMode === 'followings'
                        ? '先从关注列表选择一个 UP 主，再拉取视频标题'
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
                  onSelectAll={() =>
                    setSelectedBatchVideoIds(previewVideos.map(video => video.video_id))
                  }
                  onClear={() => setSelectedBatchVideoIds([])}
                  onToggleVideo={setPreviewVideoSelected}
                  onOpenTask={openBatchTask}
                />

                {selectedPreviewVideos.length === 0 && previewVideos.length > 0 && (
                  <div className="text-xs text-red-500">请选择至少一个视频再开始批量处理</div>
                )}

                {previewVideos.length > 0 && !previewDirty && (
                  <div className="text-xs text-neutral-500">
                    {dynamicsMode
                      ? '当前列表已锁定到这次拉取结果。修改最多视频数后，需要重新拉取才能提交。'
                      : `当前列表已锁定到这次拉取结果。修改${
                          uploaderSourceMode === 'followings' ? '所选 UP 主' : '链接'
                        }或视频数后，需要重新拉取才能提交。`}
                  </div>
                )}

                {batchStatus && (
                  <div className="rounded-md bg-neutral-50 p-3 text-xs text-neutral-700">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span>批量状态：{batchStatus.status}</span>
                      <span>
                        {batchStatus.completed || 0}/{batchStatus.total || 0}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-neutral-200">
                      <div
                        className="bg-primary h-full rounded-full transition-all"
                        style={{
                          width: `${
                            batchStatus.total
                              ? Math.round(((batchStatus.completed || 0) / batchStatus.total) * 100)
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                    {!!batchStatus.items?.some(
                      item =>
                        item.task_id && (item.status === 'SUCCESS' || item.status === 'SKIPPED')
                    ) && (
                      <div className="mt-2 text-[11px] text-neutral-500">
                        成功项已同步到历史区，也可以在列表里直接点“查看”。
                      </div>
                    )}
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

              <FormField
                control={form.control}
                name="allow_audio_transcription"
                render={({ field }) => (
                  <FormItem className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <FormLabel>无字幕时允许音频转写</FormLabel>
                        <div className="text-xs text-neutral-500">
                          关闭时只使用现成字幕；开启后找不到字幕会继续下载音频并转写。
                        </div>
                      </div>
                      <FormControl>
                        <Switch checked={!!field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </div>
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
