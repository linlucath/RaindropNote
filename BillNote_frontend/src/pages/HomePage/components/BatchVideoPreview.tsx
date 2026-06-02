import { useEffect, useEffectEvent, useMemo, useRef, type KeyboardEvent } from 'react'
import { AlertCircle, FileText, ListChecks, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge.tsx'
import {
  getUniqueBatchVideos,
  shouldToggleVideoItemFromKeydown,
} from '@/pages/HomePage/components/batchVideoSelection.ts'
import { formatBatchVideoMeta } from '@/pages/HomePage/components/batchVideoMeta.ts'
import { shouldRequestNextPage } from '@/pages/HomePage/components/progressiveBatchLoading.ts'
import type { BatchVideo } from '@/services/note.ts'

export interface BatchStatusItem {
  video_id: string
  status: string
  message?: string
  task_id?: string | null
}

export interface BatchVideoPreviewProps {
  videos: BatchVideo[]
  statusItems?: BatchStatusItem[]
  loading?: boolean
  loadingMore?: boolean
  hasMore?: boolean
  emptyMessage?: string
  stale?: boolean
  staleMessage?: string
  onLoadMore?: () => void
  onActivateVideo: (video: BatchVideo, statusItem?: BatchStatusItem) => void
}

const getVideoTitle = (video: BatchVideo) => video.title?.trim() || video.video_url
const getVideoMeta = (video: BatchVideo) => formatBatchVideoMeta(video)

const getActionLabel = (statusItem?: BatchStatusItem) => {
  if (!statusItem) {
    return '立即处理'
  }

  if (statusItem.status === 'SUCCESS') {
    return '查看结果'
  }

  if (statusItem.status === 'FAILED' || statusItem.status === 'CANCELLED') {
    return '重新处理'
  }

  return '查看进度'
}

const getStatusTone = (statusItem?: BatchStatusItem) => {
  if (!statusItem) {
    return 'border-l-transparent hover:bg-neutral-50'
  }

  if (statusItem.status === 'SUCCESS') {
    return 'border-l-emerald-500 bg-emerald-50/40 hover:bg-emerald-50/60'
  }

  if (statusItem.status === 'FAILED' || statusItem.status === 'CANCELLED') {
    return 'border-l-amber-500 bg-amber-50/40 hover:bg-amber-50/60'
  }

  return 'border-l-sky-500 bg-sky-50/50 hover:bg-sky-50/70'
}

export default function BatchVideoPreview({
  videos,
  statusItems = [],
  loading = false,
  loadingMore = false,
  hasMore = false,
  emptyMessage = '暂无视频标题',
  stale = false,
  staleMessage = '当前列表已过期，请刷新后继续',
  onLoadMore,
  onActivateVideo,
}: BatchVideoPreviewProps) {
  const uniqueVideos = useMemo(() => getUniqueBatchVideos(videos), [videos])
  const statusByVideoId = useMemo(
    () => new Map(statusItems.map(item => [item.video_id, item])),
    [statusItems]
  )
  const listRef = useRef<HTMLDivElement | null>(null)
  const autoLoadMoreLockedRef = useRef(false)
  const completedCount = statusItems.filter(item => item.status === 'SUCCESS').length

  useEffect(() => {
    if (!loadingMore) {
      autoLoadMoreLockedRef.current = false
    }
  }, [loadingMore])

  const maybeAutoLoadMore = useEffectEvent(() => {
    const listElement = listRef.current
    if (!listElement || !onLoadMore || autoLoadMoreLockedRef.current) {
      return
    }

    if (
      !shouldRequestNextPage({
        hasMore,
        loading,
        loadingMore,
        scrollTop: listElement.scrollTop,
        clientHeight: listElement.clientHeight,
        scrollHeight: listElement.scrollHeight,
      })
    ) {
      return
    }

    autoLoadMoreLockedRef.current = true
    onLoadMore()
  })

  useEffect(() => {
    if (uniqueVideos.length === 0) {
      return
    }

    maybeAutoLoadMore()
  }, [hasMore, loading, loadingMore, maybeAutoLoadMore, uniqueVideos.length])

  const handleVideoItemKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    video: BatchVideo,
    statusItem?: BatchStatusItem
  ) => {
    if (
      !shouldToggleVideoItemFromKeydown({
        key: event.key,
        targetIsCurrentTarget: event.target === event.currentTarget,
      })
    ) {
      return
    }

    event.preventDefault()
    onActivateVideo(video, statusItem)
  }

  return (
    <div className="space-y-3">
      {stale && videos.length > 0 ? (
        <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-medium">需要刷新</div>
            <p className="mt-0.5 text-xs leading-5 text-amber-800">{staleMessage}</p>
          </div>
        </div>
      ) : null}

      {loading && videos.length === 0 ? (
        <div className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-200 bg-neutral-50/70 px-4 py-6 text-center">
          <Loader2 className="h-4 w-4 animate-spin text-neutral-400" />
          <span className="text-sm text-neutral-500">正在拉取视频标题</span>
        </div>
      ) : videos.length === 0 ? (
        <div className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-200 bg-neutral-50/50 px-4 py-6 text-center">
          <FileText className="h-4 w-4 text-neutral-400" />
          <span className="text-sm text-neutral-500">{emptyMessage}</span>
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-neutral-200 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-neutral-200 bg-neutral-50 px-3 py-2.5">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-2">
                <ListChecks className="h-4 w-4 shrink-0 text-neutral-500" />
                <span className="text-sm font-medium text-neutral-800">视频标题预览</span>
                {stale ? (
                  <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800">
                    待刷新
                  </Badge>
                ) : null}
              </div>
              {completedCount > 0 ? (
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                  <span>已有 {completedCount} 条结果可查看</span>
                </div>
              ) : null}
            </div>
          </div>

          <div
            ref={listRef}
            className="max-h-[28rem] divide-y divide-neutral-100 overflow-y-auto"
            onScroll={() => {
              maybeAutoLoadMore()
            }}
          >
            {uniqueVideos.map((video, index) => {
              const statusItem = statusByVideoId.get(video.video_id)

              return (
                <div
                  key={video.video_id}
                  role="button"
                  tabIndex={0}
                  className={`grid cursor-pointer grid-cols-[auto_minmax(0,1fr)_auto] gap-3 border-l-2 px-3 py-3.5 transition-colors ${getStatusTone(
                    statusItem
                  )}`}
                  title={video.video_id}
                  onClick={() => onActivateVideo(video, statusItem)}
                  onKeyDown={event => handleVideoItemKeyDown(event, video, statusItem)}
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-[11px] text-neutral-400 tabular-nums shadow-sm">
                    {index + 1}
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-sm leading-5 font-medium text-neutral-900">
                      {getVideoTitle(video)}
                    </span>
                    {getVideoMeta(video) ? (
                      <span className="mt-1 block text-xs text-neutral-500">{getVideoMeta(video)}</span>
                    ) : null}
                    {statusItem ? (
                      <span className="mt-1.5 flex min-w-0 items-center gap-2 text-xs text-neutral-500">
                        <Badge
                          variant="outline"
                          className="h-5 bg-white px-1.5 text-[10px] text-neutral-600"
                          title={statusItem.message}
                        >
                          {statusItem.status}
                        </Badge>
                        {statusItem.message ? (
                          <span className="truncate text-[11px] text-neutral-500">
                            {statusItem.message}
                          </span>
                        ) : null}
                      </span>
                    ) : null}
                  </span>
                  <span className="self-center rounded-full border border-neutral-200 bg-white px-2.5 py-1 text-xs text-neutral-600">
                    {getActionLabel(statusItem)}
                  </span>
                </div>
              )
            })}
          </div>
          {hasMore && onLoadMore && loadingMore ? (
            <div className="flex items-center justify-center gap-2 border-t border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>正在加载更多</span>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
