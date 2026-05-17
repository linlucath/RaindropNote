import { useEffect, useMemo, useRef, type KeyboardEvent } from 'react'
import { AlertCircle, ArrowUpRight, FileText, ListChecks, Loader2, RefreshCw } from 'lucide-react'

import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Checkbox } from '@/components/ui/checkbox.tsx'
import {
  getUniqueBatchVideos,
  shouldToggleVideoItemFromKeydown,
} from '@/pages/HomePage/components/batchVideoSelection.ts'
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
  selectedVideoIds: string[]
  statusItems?: BatchStatusItem[]
  loading?: boolean
  loadingMore?: boolean
  hasMore?: boolean
  showPreviewButton?: boolean
  emptyMessage?: string
  stale?: boolean
  staleMessage?: string
  onPreview: () => void
  onLoadMore?: () => void
  onSelectAll: () => void
  onClear: () => void
  onToggleVideo: (videoId: string, checked: boolean) => void
  onOpenTask?: (taskId: string) => void
}

const getVideoTitle = (video: BatchVideo) => video.title?.trim() || video.video_url
const getVideoMeta = (video: BatchVideo) => {
  const authorName = video.author_name?.trim()
  return authorName ? authorName : ''
}

export default function BatchVideoPreview({
  videos,
  selectedVideoIds,
  statusItems = [],
  loading = false,
  loadingMore = false,
  hasMore = false,
  showPreviewButton = true,
  emptyMessage = '先拉取视频列表',
  stale = false,
  staleMessage = '当前列表已过期，请重新拉取',
  onPreview,
  onLoadMore,
  onSelectAll,
  onClear,
  onToggleVideo,
  onOpenTask,
}: BatchVideoPreviewProps) {
  const uniqueVideos = useMemo(() => getUniqueBatchVideos(videos), [videos])
  const selectedIdSet = useMemo(() => new Set(selectedVideoIds), [selectedVideoIds])
  const statusByVideoId = useMemo(
    () => new Map(statusItems.map(item => [item.video_id, item])),
    [statusItems]
  )
  const listRef = useRef<HTMLDivElement | null>(null)
  const autoLoadMoreLockedRef = useRef(false)
  const selectedCount = uniqueVideos.reduce(
    (count, video) => count + (selectedIdSet.has(video.video_id) ? 1 : 0),
    0
  )
  const allSelected = uniqueVideos.length > 0 && selectedCount === uniqueVideos.length
  const completedCount = statusItems.filter(
    item => item.status === 'SUCCESS' || item.status === 'SKIPPED'
  ).length

  useEffect(() => {
    if (!loadingMore) {
      autoLoadMoreLockedRef.current = false
    }
  }, [loadingMore])

  const maybeAutoLoadMore = () => {
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
  }

  useEffect(() => {
    if (uniqueVideos.length === 0) {
      return
    }

    maybeAutoLoadMore()
  }, [hasMore, loading, loadingMore, uniqueVideos.length])

  const handleVideoItemKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    videoId: string,
    selected: boolean
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
    onToggleVideo(videoId, !selected)
  }

  return (
    <div className="space-y-3">
      {showPreviewButton ? (
        <Button
          type="button"
          variant="outline"
          className="h-10 w-full"
          disabled={loading}
          onClick={onPreview}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          拉取视频列表
        </Button>
      ) : null}

      {stale && videos.length > 0 ? (
        <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-medium">需要重新拉取</div>
            <p className="mt-0.5 text-xs leading-5 text-amber-800">{staleMessage}</p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-8 border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
            onClick={onPreview}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            重新拉取
          </Button>
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
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
                <Badge variant="outline" className="bg-white text-neutral-700">
                  已选 {selectedCount} / {uniqueVideos.length}
                </Badge>
                {uniqueVideos.length !== videos.length ? (
                  <Badge variant="outline" className="bg-white text-neutral-500">
                    已去重 {uniqueVideos.length} 条
                  </Badge>
                ) : null}
                {completedCount > 0 ? <span>已有 {completedCount} 条结果可查看</span> : null}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs"
                disabled={uniqueVideos.length === 0 || allSelected}
                onClick={onSelectAll}
              >
                全选
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs"
                disabled={selectedCount === 0}
                onClick={onClear}
              >
                全不选
              </Button>
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
              const selected = selectedIdSet.has(video.video_id)
              const statusItem = statusByVideoId.get(video.video_id)

              return (
                <div
                  key={video.video_id}
                  role="button"
                  tabIndex={0}
                  className={`grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] gap-3 border-l-2 px-3 py-3.5 transition-colors ${
                    selected
                      ? 'border-l-primary bg-sky-50/50'
                      : 'border-l-transparent hover:bg-neutral-50'
                  }`}
                  title={video.video_id}
                  onClick={() => onToggleVideo(video.video_id, !selected)}
                  onKeyDown={event => handleVideoItemKeyDown(event, video.video_id, selected)}
                >
                  <span className="flex flex-col items-center gap-2 pt-0.5">
                    <Checkbox
                      checked={selected}
                      onClick={event => event.stopPropagation()}
                      onCheckedChange={checked => onToggleVideo(video.video_id, checked === true)}
                    />
                    <span className="text-[11px] text-neutral-400 tabular-nums">{index + 1}</span>
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-start justify-between gap-3">
                      <span className="line-clamp-2 text-sm leading-5 font-medium text-neutral-900">
                        {getVideoTitle(video)}
                      </span>
                      {statusItem?.task_id &&
                      (statusItem.status === 'SUCCESS' || statusItem.status === 'SKIPPED') &&
                      onOpenTask ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="mt-0.5 h-7 shrink-0 px-2 text-xs text-neutral-600"
                          onClick={event => {
                            event.preventDefault()
                            event.stopPropagation()
                            onOpenTask(statusItem.task_id as string)
                          }}
                        >
                          查看
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </Button>
                      ) : null}
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
                </div>
              )
            })}
          </div>
          {hasMore && onLoadMore ? (
            <div className="border-t border-neutral-200 bg-neutral-50 px-3 py-2">
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                disabled={loadingMore}
                onClick={onLoadMore}
              >
                {loadingMore ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                加载更多
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
