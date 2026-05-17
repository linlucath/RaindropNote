import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Bookmark, Copy, Download, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import gfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import 'github-markdown-css/github-markdown-light.css'

import { Button } from '@/components/ui/button.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { cn } from '@/lib/utils.ts'
import {
  deleteFavorite,
  FavoriteTranscriptItem,
  listFavorites,
} from '@/services/favorite.ts'
import TranscriptViewer from '@/pages/HomePage/components/transcriptViewer.tsx'

const remarkPlugins = [gfm, remarkMath]
const rehypePlugins = [rehypeKatex]

const formatDateTime = (value?: string | null) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const FavoritesPage = () => {
  const [favorites, setFavorites] = useState<FavoriteTranscriptItem[]>([])
  const [selectedFavoriteId, setSelectedFavoriteId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [showTranscript, setShowTranscript] = useState(false)

  useEffect(() => {
    let cancelled = false

    listFavorites()
      .then(({ favorites: items }) => {
        if (cancelled) return
        setFavorites(items)
        setSelectedFavoriteId(currentId => currentId ?? items[0]?.id ?? null)
      })
      .catch(error => console.warn('加载收藏列表失败', error))

    return () => {
      cancelled = true
    }
  }, [])

  const filteredFavorites = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) return favorites
    return favorites.filter(item => item.title.toLowerCase().includes(keyword))
  }, [favorites, search])

  useEffect(() => {
    if (!filteredFavorites.length) {
      setSelectedFavoriteId(null)
      return
    }

    if (!filteredFavorites.some(item => item.id === selectedFavoriteId)) {
      setSelectedFavoriteId(filteredFavorites[0].id)
    }
  }, [filteredFavorites, selectedFavoriteId])

  const selectedFavorite =
    filteredFavorites.find(item => item.id === selectedFavoriteId) ??
    favorites.find(item => item.id === selectedFavoriteId) ??
    null

  const handleCopy = async () => {
    if (!selectedFavorite?.markdown) return
    await navigator.clipboard.writeText(selectedFavorite.markdown)
  }

  const handleDownload = () => {
    if (!selectedFavorite) return

    const blob = new Blob([selectedFavorite.markdown], { type: 'text/markdown;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${selectedFavorite.title || 'favorite-transcript'}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleDelete = async (favoriteId: number) => {
    await deleteFavorite(favoriteId)

    setFavorites(current => {
      const next = current.filter(item => item.id !== favoriteId)
      if (selectedFavoriteId === favoriteId) {
        setSelectedFavoriteId(next[0]?.id ?? null)
      }
      return next
    })
  }

  return (
    <div className="flex h-screen flex-col bg-neutral-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Button asChild variant="ghost" size="sm">
              <Link to="/">
                <ArrowLeft className="h-4 w-4" />
                返回首页
              </Link>
            </Button>
            <div>
              <div className="flex items-center gap-2 text-lg font-semibold text-neutral-900">
                <Bookmark className="h-5 w-5" />
                收藏页
              </div>
              <p className="text-sm text-neutral-500">查看已收藏的文字稿副本</p>
            </div>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/progress">任务进度</Link>
          </Button>
        </div>
      </header>

      <div className="mx-auto flex h-full w-full max-w-[1600px] gap-4 overflow-hidden p-4">
        <aside className="flex h-full w-[340px] shrink-0 flex-col rounded-xl border bg-white">
          <div className="border-b px-4 py-4">
            <div className="mb-3 text-sm font-medium text-neutral-800">已收藏文字稿</div>
            <input
              type="text"
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="搜索收藏标题..."
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>

          <ScrollArea className="flex-1">
            <div className="space-y-2 p-3">
              {!filteredFavorites.length ? (
                <div className="rounded-lg border border-dashed border-neutral-200 bg-neutral-50 px-4 py-8 text-center text-sm text-neutral-500">
                  暂无收藏
                </div>
              ) : (
                filteredFavorites.map(item => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedFavoriteId(item.id)}
                    className={cn(
                      'w-full rounded-lg border px-3 py-3 text-left transition-colors',
                      selectedFavoriteId === item.id
                        ? 'border-primary bg-primary/5'
                        : 'border-neutral-200 hover:bg-neutral-50'
                    )}
                  >
                    <div className="line-clamp-2 text-sm font-medium text-neutral-900">
                      {item.title}
                    </div>
                    <div className="mt-2 text-xs text-neutral-500">
                      收藏于 {formatDateTime(item.updated_at || item.created_at)}
                    </div>
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </aside>

        <main className="flex min-w-0 flex-1 gap-4 overflow-hidden">
          <section className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
            {!selectedFavorite ? (
              <div className="flex h-full items-center justify-center text-sm text-neutral-500">
                选择一篇收藏的文字稿查看内容
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
                  <div>
                    <h1 className="text-lg font-semibold text-neutral-900">{selectedFavorite.title}</h1>
                    <p className="mt-1 text-sm text-neutral-500">
                      收藏时间 {formatDateTime(selectedFavorite.updated_at || selectedFavorite.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={handleCopy}>
                      <Copy className="h-4 w-4" />
                      复制
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleDownload}>
                      <Download className="h-4 w-4" />
                      导出 Markdown
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowTranscript(current => !current)}
                    >
                      原文参照
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(selectedFavorite.id)}>
                      <Trash2 className="h-4 w-4" />
                      取消收藏
                    </Button>
                  </div>
                </div>

                <div className="flex min-h-0 flex-1">
                  <ScrollArea className="min-w-0 flex-1">
                    <article className="markdown-body px-6 py-6">
                      <ReactMarkdown
                        remarkPlugins={remarkPlugins}
                        rehypePlugins={rehypePlugins}
                      >
                        {selectedFavorite.markdown}
                      </ReactMarkdown>
                    </article>
                  </ScrollArea>

                  {showTranscript ? (
                    <div className="hidden w-[360px] shrink-0 border-l p-4 xl:block">
                      <TranscriptViewer transcript={selectedFavorite.transcript ?? undefined} />
                    </div>
                  ) : null}
                </div>
              </>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}

export default FavoritesPage
