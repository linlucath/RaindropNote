import { useEffect, useEffectEvent, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { AlertCircle, Loader2, RefreshCw, UserRound } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert.tsx'
import { Button } from '@/components/ui/button.tsx'
import { getDownloaderCookie } from '@/services/downloader.ts'
import {
  FollowingUploader,
  FollowingUploaderPage,
  getBilibiliFollowings,
} from '@/services/note.ts'
import { shouldRequestNextPage } from '@/pages/HomePage/components/progressiveBatchLoading.ts'

interface FollowingUploaderPickerProps {
  selectedMid?: string
  initialPageData?: FollowingUploaderPage | null
  preloading?: boolean
  onSelectUploader: (uploader: FollowingUploader) => void
}

type RequestError = {
  msg?: string
}

const DEFAULT_PAGE_SIZE = 20

export default function FollowingUploaderPicker({
  selectedMid,
  initialPageData = null,
  preloading = false,
  onSelectUploader,
}: FollowingUploaderPickerProps) {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [items, setItems] = useState<FollowingUploader[]>([])
  const [error, setError] = useState<string>('')
  const listRef = useRef<HTMLDivElement | null>(null)
  const hydratedInitialDataRef = useRef(false)
  const attemptedInitialLoadRef = useRef(false)
  const autoLoadMoreLockedRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    getDownloaderCookie('bilibili')
      .then(data => {
        if (!cancelled) {
          setConfigured(!!data?.cookie)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConfigured(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!initialPageData || hydratedInitialDataRef.current) {
      return
    }

    hydratedInitialDataRef.current = true
    attemptedInitialLoadRef.current = true
    setItems(initialPageData.items)
    setPage(initialPageData.page)
    setHasMore(initialPageData.has_more)
    setError('')
  }, [initialPageData])

  useEffect(() => {
    if (!loadingMore) {
      autoLoadMoreLockedRef.current = false
    }
  }, [loadingMore])

  const emptyMessage = useMemo(() => {
    if (error) return error
    if (configured === false) return '请先到设置页填写 Bilibili Cookie'
    return '当前账号暂无可读取的关注 UP 主'
  }, [configured, error])
  const showInitialLoading = loading || (preloading && items.length === 0)

  const loadFollowings = async (nextPage: number, reset = false) => {
    const setter = reset ? setLoading : setLoadingMore
    setter(true)
    setError('')
    try {
      const data = (await getBilibiliFollowings({
        page: nextPage,
        page_size: DEFAULT_PAGE_SIZE,
      })) as FollowingUploaderPage
      setItems(current => (reset ? data.items : [...current, ...data.items]))
      setPage(data.page)
      setHasMore(data.has_more)
    } catch (loadError: unknown) {
      const message =
        (typeof loadError === 'object' && loadError !== null && 'msg' in loadError
          ? (loadError as RequestError).msg
          : '') || '拉取关注列表失败，请稍后重试'
      setError(message)
    } finally {
      setter(false)
    }
  }

  const handleRefresh = async () => {
    await loadFollowings(1, true)
  }

  const handleLoadMore = async () => {
    await loadFollowings(page + 1, false)
  }

  const maybeAutoLoadMore = useEffectEvent(() => {
    const listElement = listRef.current
    if (!listElement || autoLoadMoreLockedRef.current) {
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
    void handleLoadMore()
  })

  useEffect(() => {
    if (configured !== true || preloading || attemptedInitialLoadRef.current || items.length > 0) {
      return
    }

    attemptedInitialLoadRef.current = true
    void loadFollowings(1, true)
  }, [configured, items.length, preloading])

  useEffect(() => {
    if (items.length === 0) {
      return
    }

    maybeAutoLoadMore()
  }, [hasMore, items.length, loading, loadingMore, maybeAutoLoadMore])

  const handleUploaderItemKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    uploader: FollowingUploader
  ) => {
    if (event.target !== event.currentTarget) {
      return
    }

    if (event.key !== 'Enter' && event.key !== ' ') {
      return
    }

    event.preventDefault()
    if (uploader.mid === selectedMid) {
      return
    }
    onSelectUploader(uploader)
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button
          type="button"
          variant="outline"
          className="h-10 px-3"
          disabled={showInitialLoading || configured === false}
          onClick={() => void handleRefresh()}
        >
          {showInitialLoading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          拉取关注列表
        </Button>
      </div>

      {configured === false ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>请先到设置页填写 Bilibili Cookie，才能读取已关注的 UP 主列表。</AlertDescription>
        </Alert>
      ) : null}

      {items.length === 0 ? (
        <div className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-neutral-200 bg-neutral-50/50 px-4 py-6 text-center">
          {showInitialLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-neutral-400" />
          ) : (
            <UserRound className="h-4 w-4 text-neutral-400" />
          )}
          <span className="text-sm text-neutral-500">{emptyMessage}</span>
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-neutral-200 bg-white">
          <div
            ref={listRef}
            className="max-h-72 divide-y divide-neutral-100 overflow-y-auto"
            onScroll={() => {
              maybeAutoLoadMore()
            }}
          >
            {items.map(item => {
              const selected = item.mid === selectedMid
              return (
                <div
                  key={item.mid}
                  role="button"
                  tabIndex={0}
                  className={`grid w-full grid-cols-[auto_minmax(0,1fr)] gap-3 px-3 py-3 text-left transition-colors ${
                    selected ? 'bg-sky-50' : 'hover:bg-neutral-50'
                  }`}
                  onClick={() => {
                    if (selected) {
                      return
                    }
                    onSelectUploader(item)
                  }}
                  onKeyDown={event => handleUploaderItemKeyDown(event, item)}
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-neutral-100 text-neutral-400">
                    <UserRound className="h-4 w-4" />
                  </div>
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-neutral-900">{item.name}</span>
                      {selected ? (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] text-sky-700">
                          已选择
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-1 line-clamp-2 block text-xs leading-5 text-neutral-500">
                      {item.sign || '这个 UP 主还没有填写简介'}
                    </span>
                  </span>
                </div>
              )
            })}
          </div>
          {hasMore ? (
            <div className="border-t border-neutral-200 bg-neutral-50 px-3 py-2">
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                disabled={loadingMore}
                onClick={() => void handleLoadMore()}
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
