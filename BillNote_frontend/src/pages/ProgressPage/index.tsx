import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Clock3,
  Loader2,
  Square,
  RefreshCw,
  ListTree,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import {
  BatchStatus,
  cancelBatch,
  cancelTask,
  get_task_list,
  getProgressOverview,
  ProgressBatchItem,
  ProgressOverview,
  ProgressTaskItem,
  RuntimeTaskStatus,
} from '@/services/note.ts'
import { useTaskStore } from '@/store/taskStore'

const ACTIVE_TASK_STATUSES: RuntimeTaskStatus[] = [
  'PENDING',
  'PARSING',
  'DOWNLOADING',
  'TRANSCRIBING',
  'SUMMARIZING',
  'FORMATTING',
  'SAVING',
  'CANCELLING',
]
const ACTIVE_BATCH_STATUSES: BatchStatus[] = ['PENDING', 'RUNNING', 'CANCELLING']

const emptyOverview: ProgressOverview = {
  summary: {
    pending: 0,
    running: 0,
    cancelling: 0,
    success: 0,
    failed: 0,
    cancelled: 0,
  },
  tasks: {
    active: [],
    recent_terminal: [],
  },
  batches: {
    active: [],
    recent_terminal: [],
  },
}

const statusLabelMap: Record<string, string> = {
  PENDING: '排队中',
  PARSING: '解析链接',
  DOWNLOADING: '下载中',
  TRANSCRIBING: '转写中',
  SUMMARIZING: '总结中',
  FORMATTING: '格式化中',
  SAVING: '保存中',
  SUCCESS: '已完成',
  FAILED: '失败',
  CANCELLING: '正在停止',
  CANCELLED: '已取消',
  RUNNING: '进行中',
  SKIPPED: '已跳过',
}

const statusBadgeClassMap: Record<string, string> = {
  PENDING: 'border-amber-200 bg-amber-50 text-amber-900',
  PARSING: 'border-sky-200 bg-sky-50 text-sky-800',
  DOWNLOADING: 'border-sky-200 bg-sky-50 text-sky-800',
  TRANSCRIBING: 'border-sky-200 bg-sky-50 text-sky-800',
  SUMMARIZING: 'border-sky-200 bg-sky-50 text-sky-800',
  FORMATTING: 'border-sky-200 bg-sky-50 text-sky-800',
  SAVING: 'border-sky-200 bg-sky-50 text-sky-800',
  RUNNING: 'border-sky-200 bg-sky-50 text-sky-800',
  SUCCESS: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  FAILED: 'border-rose-200 bg-rose-50 text-rose-800',
  CANCELLING: 'border-orange-200 bg-orange-50 text-orange-800',
  CANCELLED: 'border-neutral-200 bg-neutral-100 text-neutral-700',
  SKIPPED: 'border-neutral-200 bg-neutral-100 text-neutral-700',
}

const summaryCards = [
  { key: 'pending', label: '排队中' },
  { key: 'running', label: '进行中' },
  { key: 'cancelling', label: '正在停止' },
  { key: 'success', label: '已完成' },
  { key: 'failed', label: '已失败' },
  { key: 'cancelled', label: '已取消' },
] as const

const formatTime = (value?: string) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const isTaskActive = (status: RuntimeTaskStatus) => ACTIVE_TASK_STATUSES.includes(status)
const isBatchActive = (status: BatchStatus) => ACTIVE_BATCH_STATUSES.includes(status)

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={`h-6 rounded-full px-2 text-[11px] font-medium ${statusBadgeClassMap[status] ?? 'bg-white text-neutral-700'}`}
    >
      {statusLabelMap[status] ?? status}
    </Badge>
  )
}

function SummaryStrip({ overview }: { overview: ProgressOverview }) {
  return (
    <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
      {summaryCards.map(item => (
        <div key={item.key} className="rounded-md border border-neutral-200 bg-white px-4 py-3">
          <div className="text-xs text-neutral-500">{item.label}</div>
          <div className="mt-2 text-2xl font-semibold text-neutral-900">
            {overview.summary[item.key]}
          </div>
        </div>
      ))}
    </section>
  )
}

function TaskCard({
  task,
  onCancel,
  onOpen,
}: {
  task: ProgressTaskItem
  onCancel: (taskId: string) => void
  onOpen: (taskId: string) => void
}) {
  const active = isTaskActive(task.status)
  const canOpen = task.status === 'SUCCESS' && task.has_result

  return (
    <article className="rounded-md border border-neutral-200 bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-neutral-900">{task.title || '未命名任务'}</h3>
            <StatusBadge status={task.status} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-neutral-500">
            <span>{task.platform || '未知来源'}</span>
            <span>创建于 {formatTime(task.created_at)}</span>
            <span>更新于 {formatTime(task.updated_at)}</span>
          </div>
          {task.message ? <p className="mt-2 text-sm text-neutral-600">{task.message}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {canOpen ? (
            <Button type="button" variant="outline" size="sm" onClick={() => onOpen(task.task_id)}>
              查看结果
            </Button>
          ) : null}
          {active && task.status !== 'CANCELLING' ? (
            <Button type="button" variant="outline" size="sm" onClick={() => onCancel(task.task_id)}>
              <Square className="h-3.5 w-3.5" />
              结束任务
            </Button>
          ) : null}
        </div>
      </div>
    </article>
  )
}

function BatchCard({
  batch,
  expanded,
  onToggle,
  onCancel,
  onOpenTask,
}: {
  batch: ProgressBatchItem
  expanded: boolean
  onToggle: () => void
  onCancel: (batchId: string) => void
  onOpenTask: (taskId: string) => void
}) {
  const active = isBatchActive(batch.status)

  return (
    <article className="rounded-md border border-neutral-200 bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onToggle}
              className="flex items-center gap-1 text-left text-sm font-semibold text-neutral-900"
            >
              {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <span>{batch.title || '批量任务'}</span>
            </button>
            <StatusBadge status={batch.status} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-neutral-500">
            <span>{batch.source_label || '未知来源'}</span>
            <span>
              进度 {batch.completed} / {batch.total}
            </span>
            <span>更新于 {formatTime(batch.updated_at)}</span>
          </div>
          {batch.current_item_title ? (
            <p className="mt-2 text-sm text-neutral-600">当前正在处理：{batch.current_item_title}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {active && batch.status !== 'CANCELLING' ? (
            <Button type="button" variant="outline" size="sm" onClick={() => onCancel(batch.batch_id)}>
              <Square className="h-3.5 w-3.5" />
              停止批量
            </Button>
          ) : null}
        </div>
      </div>

      {expanded && batch.items?.length ? (
        <div className="mt-4 overflow-hidden rounded-md border border-neutral-200">
          <div className="divide-y divide-neutral-100">
            {batch.items.map((item, index) => (
              <div key={`${batch.batch_id}-${item.video_id}-${index}`} className="flex items-start justify-between gap-3 px-3 py-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-neutral-900">{item.title || item.video_id}</span>
                    <StatusBadge status={item.status} />
                  </div>
                  {item.message ? <p className="mt-1 text-xs text-neutral-500">{item.message}</p> : null}
                </div>
                {item.task_id && (item.status === 'SUCCESS' || item.status === 'SKIPPED') ? (
                  <Button type="button" variant="ghost" size="sm" onClick={() => onOpenTask(item.task_id as string)}>
                    查看
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  )
}

export default function ProgressPage() {
  const navigate = useNavigate()
  const syncSavedTasks = useTaskStore(state => state.syncSavedTasks)
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)
  const [overview, setOverview] = useState<ProgressOverview>(emptyOverview)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [showActiveOnly, setShowActiveOnly] = useState(true)
  const [showBatches, setShowBatches] = useState(true)
  const [expandedBatchIds, setExpandedBatchIds] = useState<string[]>([])

  const loadOverview = useCallback(
    async (silent = false) => {
      if (!silent) {
        setRefreshing(true)
      }
      try {
        const data = await getProgressOverview()
        setOverview(data)
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    []
  )

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  useEffect(() => {
    const hasActive =
      overview.tasks.active.length > 0 || overview.batches.active.length > 0 || loading
    if (!hasActive) return

    const timer = window.setInterval(() => {
      loadOverview(true)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [loading, loadOverview, overview.batches.active.length, overview.tasks.active.length])

  const openTask = useCallback(
    async (taskId: string) => {
      const res = await get_task_list()
      syncSavedTasks(res?.tasks || [])
      setCurrentTask(taskId)
      navigate('/')
    },
    [navigate, setCurrentTask, syncSavedTasks]
  )

  const handleCancelTask = useCallback(
    async (taskId: string) => {
      if (!window.confirm('结束后，这个任务会在安全检查点停止。继续吗？')) return
      await cancelTask(taskId)
      setOverview(current => ({
        ...current,
        tasks: {
          ...current.tasks,
          active: current.tasks.active.map(task =>
            task.task_id === taskId ? { ...task, status: 'CANCELLING', message: '正在停止' } : task
          ),
          recent_terminal: current.tasks.recent_terminal,
        },
      }))
      await loadOverview(true)
    },
    [loadOverview]
  )

  const handleCancelBatch = useCallback(
    async (batchId: string) => {
      if (!window.confirm('停止后，当前批次不会继续启动后续任务。继续吗？')) return
      await cancelBatch(batchId)
      setOverview(current => ({
        ...current,
        batches: {
          ...current.batches,
          active: current.batches.active.map(batchItem =>
            batchItem.batch_id === batchId
              ? { ...batchItem, status: 'CANCELLING', cancel_requested: true }
              : batchItem
          ),
          recent_terminal: current.batches.recent_terminal,
        },
      }))
      await loadOverview(true)
    },
    [loadOverview]
  )

  const visibleTasks = useMemo(
    () =>
      showActiveOnly
        ? overview.tasks.active
        : [...overview.tasks.active, ...overview.tasks.recent_terminal],
    [overview.tasks.active, overview.tasks.recent_terminal, showActiveOnly]
  )
  const visibleBatches = useMemo(
    () =>
      showActiveOnly
        ? overview.batches.active
        : [...overview.batches.active, ...overview.batches.recent_terminal],
    [overview.batches.active, overview.batches.recent_terminal, showActiveOnly]
  )

  return (
    <div className="flex h-screen flex-col bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link to="/" className="inline-flex">
              <Button type="button" variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4" />
                返回工作台
              </Button>
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-neutral-500" />
                <h1 className="text-lg font-semibold text-neutral-900">任务进度</h1>
              </div>
              <p className="mt-1 text-sm text-neutral-500">集中查看正在处理的任务，也能在这里停止它们。</p>
            </div>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => loadOverview()} disabled={refreshing}>
            {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            刷新
          </Button>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-6 py-6">
          <SummaryStrip overview={overview} />

          <section className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant={showActiveOnly ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowActiveOnly(true)}
            >
              只看活跃任务
            </Button>
            <Button
              type="button"
              variant={!showActiveOnly ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowActiveOnly(false)}
            >
              显示最近终态
            </Button>
            <Button
              type="button"
              variant={showBatches ? 'outline' : 'ghost'}
              size="sm"
              onClick={() => setShowBatches(value => !value)}
            >
              <ListTree className="h-4 w-4" />
              {showBatches ? '隐藏批量任务' : '显示批量任务'}
            </Button>
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Clock3 className="h-4 w-4 text-neutral-500" />
                <h2 className="text-sm font-semibold text-neutral-800">单任务</h2>
              </div>
              {loading ? (
                <div className="flex min-h-40 items-center justify-center rounded-md border border-neutral-200 bg-white">
                  <Loader2 className="h-5 w-5 animate-spin text-neutral-400" />
                </div>
              ) : visibleTasks.length ? (
                visibleTasks.map(task => (
                  <TaskCard key={task.task_id} task={task} onCancel={handleCancelTask} onOpen={openTask} />
                ))
              ) : (
                <div className="rounded-md border border-dashed border-neutral-200 bg-white px-4 py-10 text-center text-sm text-neutral-500">
                  这里暂时没有任务。
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <ListTree className="h-4 w-4 text-neutral-500" />
                <h2 className="text-sm font-semibold text-neutral-800">批量任务</h2>
              </div>
              {!showBatches ? (
                <div className="rounded-md border border-dashed border-neutral-200 bg-white px-4 py-10 text-center text-sm text-neutral-500">
                  已隐藏批量任务列表。
                </div>
              ) : visibleBatches.length ? (
                visibleBatches.map(batch => (
                  <BatchCard
                    key={batch.batch_id}
                    batch={batch}
                    expanded={expandedBatchIds.includes(batch.batch_id)}
                    onToggle={() =>
                      setExpandedBatchIds(current =>
                        current.includes(batch.batch_id)
                          ? current.filter(id => id !== batch.batch_id)
                          : [...current, batch.batch_id]
                      )
                    }
                    onCancel={handleCancelBatch}
                    onOpenTask={openTask}
                  />
                ))
              ) : (
                <div className="rounded-md border border-dashed border-neutral-200 bg-white px-4 py-10 text-center text-sm text-neutral-500">
                  这里暂时没有批量任务。
                </div>
              )}
            </div>
          </section>
        </div>
      </ScrollArea>
    </div>
  )
}
