import {
  useState,
  useEffect,
  useMemo,
  useRef,
  memo,
  type FC,
  type KeyboardEvent,
  type MouseEvent,
} from 'react'
import ReactMarkdown from 'react-markdown'
import { Button } from '@/components/ui/button.tsx'
import { Copy, ArrowRight, Play, ExternalLink } from 'lucide-react'
import { toast } from 'react-hot-toast'
import Error from '@/components/Lottie/error.tsx'
import Loading from '@/components/Lottie/Loading.tsx'
import Idle from '@/components/Lottie/Idle.tsx'
import StepBar from '@/pages/HomePage/components/StepBar.tsx'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { atomDark as codeStyle } from 'react-syntax-highlighter/dist/esm/styles/prism'
import Zoom from 'react-medium-image-zoom'
import 'react-medium-image-zoom/dist/styles.css'
import gfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import 'github-markdown-css/github-markdown-light.css'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { useTaskStore } from '@/store/taskStore'
import { MarkdownHeader } from '@/pages/HomePage/components/MarkdownHeader.tsx'
import TranscriptViewer from '@/pages/HomePage/components/transcriptViewer.tsx'
import VideoBanner from '@/pages/HomePage/components/VideoBanner.tsx'
import {
  joinMarkdownBlocks,
  replaceMarkdownBlock,
  restoreSourceLink,
  splitMarkdownIntoBlocks,
  stripSourceLink,
} from '@/pages/HomePage/components/markdownBlocks.ts'
import { updateTaskMarkdown } from '@/services/note.ts'
import {
  createFavorite,
  deleteFavorite,
  getFavoriteByTask,
} from '@/services/favorite.ts'

interface MarkdownViewerProps {
  status: 'idle' | 'loading' | 'success' | 'failed'
}

const steps = [
  { label: '解析链接', key: 'PARSING' },
  { label: '下载音频', key: 'DOWNLOADING' },
  { label: '转写文字', key: 'TRANSCRIBING' },
  { label: '校对文字', key: 'SUMMARIZING' },
  { label: '保存完成', key: 'SUCCESS' },
]

const remarkPlugins = [gfm, remarkMath]
const rehypePlugins = [rehypeKatex]

/**
 * 构建 ReactMarkdown components 对象，baseURL 用于修正图片路径。
 * 使用函数 + useMemo 避免每次渲染都创建新的函数实例。
 */
function createMarkdownComponents(baseURL: string) {
  return {
    h1: ({ children, ...props }: any) => (
      <h1
        className="text-primary my-6 scroll-m-20 text-3xl font-extrabold tracking-tight lg:text-4xl"
        {...props}
      >
        {children}
      </h1>
    ),
    h2: ({ children, ...props }: any) => (
      <h2
        className="text-primary mt-10 mb-4 scroll-m-20 border-b pb-2 text-2xl font-semibold tracking-tight first:mt-0"
        {...props}
      >
        {children}
      </h2>
    ),
    h3: ({ children, ...props }: any) => (
      <h3
        className="text-primary mt-8 mb-4 scroll-m-20 text-xl font-semibold tracking-tight"
        {...props}
      >
        {children}
      </h3>
    ),
    h4: ({ children, ...props }: any) => (
      <h4
        className="text-primary mt-6 mb-2 scroll-m-20 text-lg font-semibold tracking-tight"
        {...props}
      >
        {children}
      </h4>
    ),
    p: ({ children, ...props }: any) => (
      <p className="leading-7 [&:not(:first-child)]:mt-6" {...props}>
        {children}
      </p>
    ),
    a: ({ href, children, ...props }: any) => {
      const isOriginLink =
        typeof children[0] === 'string' && (children[0] as string).startsWith('原片 @')

      if (isOriginLink) {
        const timeMatch = (children[0] as string).match(/原片 @ (\d{2}:\d{2})/)
        const timeText = timeMatch ? timeMatch[1] : '原片'

        return (
          <span className="origin-link my-2 inline-flex">
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100"
              {...props}
            >
              <Play className="h-3.5 w-3.5" />
              <span>原片（{timeText}）</span>
            </a>
          </span>
        )
      }

      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:text-primary/80 inline-flex items-center gap-0.5 font-medium underline underline-offset-4"
          {...props}
        >
          {children}
          {href?.startsWith('http') && <ExternalLink className="ml-0.5 inline-block h-3 w-3" />}
        </a>
      )
    },
    img: ({ ...props }: any) => {
      let src = props.src
      if (src.startsWith('/')) {
        src = baseURL + src
      }
      props.src = src

      return (
        <div className="my-8 flex justify-center">
          <Zoom>
            <img
              {...props}
              className="max-w-full cursor-zoom-in rounded-lg object-cover shadow-md transition-all hover:shadow-lg"
              style={{ maxHeight: '500px' }}
            />
          </Zoom>
        </div>
      )
    },
    strong: ({ children, ...props }: any) => (
      <strong className="text-primary font-bold" {...props}>
        {children}
      </strong>
    ),
    li: ({ children, ordered, checked, index, ...liProps }: any) => {
      const rawText = String(children)
      const isFakeHeading = /^(\*\*.+\*\*)$/.test(rawText.trim())
      void ordered
      void checked
      void index

      if (isFakeHeading) {
        return <div className="text-primary my-4 text-lg font-bold">{children}</div>
      }

      return (
        <li className="my-1" {...liProps}>
          {children}
        </li>
      )
    },
    ul: ({ children, ordered, depth, ...listProps }: any) => {
      void ordered
      void depth
      return (
        <ul className="my-6 ml-6 list-disc [&>li]:mt-2" {...listProps}>
          {children}
        </ul>
      )
    },
    ol: ({ children, ordered, depth, ...listProps }: any) => {
      void ordered
      void depth
      return (
        <ol className="my-6 ml-6 list-decimal [&>li]:mt-2" {...listProps}>
          {children}
        </ol>
      )
    },
    blockquote: ({ children, ...props }: any) => (
      <blockquote
        className="border-primary/20 text-muted-foreground mt-6 border-l-4 pl-4 italic"
        {...props}
      >
        {children}
      </blockquote>
    ),
    code: ({ inline, className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || '')
      const codeContent = String(children).replace(/\n$/, '')

      if (!inline && match) {
        return (
          <div className="group bg-muted relative my-6 overflow-hidden rounded-lg border shadow-sm">
            <div className="bg-muted text-muted-foreground flex items-center justify-between px-4 py-1.5 text-sm font-medium">
              <div>{match[1].toUpperCase()}</div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(codeContent)
                  toast.success('代码已复制')
                }}
                className="bg-background/80 hover:bg-background flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors"
              >
                <Copy className="h-3.5 w-3.5" />
                复制
              </button>
            </div>
            <SyntaxHighlighter
              style={codeStyle}
              language={match[1]}
              PreTag="div"
              className="!bg-muted !m-0 !p-0"
              customStyle={{
                margin: 0,
                padding: '1rem',
                background: 'transparent',
                fontSize: '0.9rem',
              }}
              {...props}
            >
              {codeContent}
            </SyntaxHighlighter>
          </div>
        )
      }

      return (
        <code
          className="bg-muted relative rounded px-[0.3rem] py-[0.2rem] font-mono text-sm"
          {...props}
        >
          {children}
        </code>
      )
    },
    table: ({ children, ...props }: any) => (
      <div className="my-6 w-full overflow-y-auto">
        <table className="w-full border-collapse text-sm" {...props}>
          {children}
        </table>
      </div>
    ),
    th: ({ children, ...props }: any) => (
      <th
        className="border-muted-foreground/20 border px-4 py-2 text-left font-medium [&[align=center]]:text-center [&[align=right]]:text-right"
        {...props}
      >
        {children}
      </th>
    ),
    td: ({ children, ...props }: any) => (
      <td
        className="border-muted-foreground/20 border px-4 py-2 text-left [&[align=center]]:text-center [&[align=right]]:text-right"
        {...props}
      >
        {children}
      </td>
    ),
    hr: ({ ...props }: any) => <hr className="border-muted-foreground/20 my-8" {...props} />,
  }
}

const MarkdownViewer: FC<MarkdownViewerProps> = memo(({ status }) => {
  const [selectedContent, setSelectedContent] = useState<string>('')
  const [modelName, setModelName] = useState<string>('')
  const [createTime, setCreateTime] = useState<string>('')
  // 确保baseURL没有尾部斜杠
  const baseURL = (
    String(import.meta.env.VITE_API_BASE_URL || '').replace('/api', '') || ''
  ).replace(/\/$/, '')
  const getSelectedTask = useTaskStore.getState().getSelectedTask
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)
  const currentTask = useTaskStore(state => state.getSelectedTask())
  const taskStatus = currentTask?.status || 'PENDING'
  const retryTask = useTaskStore.getState().retryTask
  const [showTranscribe, setShowTranscribe] = useState(false)
  const [favoriteId, setFavoriteId] = useState<number | null>(null)
  const [favoritePending, setFavoritePending] = useState(false)
  const [activeBlockIndex, setActiveBlockIndex] = useState<number | null>(null)
  const [activeBlockDraft, setActiveBlockDraft] = useState('')
  const [savingBlockIndex, setSavingBlockIndex] = useState<number | null>(null)
  const activeBlockIndexRef = useRef<number | null>(null)

  // 缓存 ReactMarkdown components，仅在 baseURL 变化时重建
  const markdownComponents = useMemo(() => createMarkdownComponents(baseURL), [baseURL])
  const visibleMarkdown = useMemo(() => stripSourceLink(selectedContent), [selectedContent])
  const markdownBlocks = useMemo(() => splitMarkdownIntoBlocks(visibleMarkdown), [visibleMarkdown])

  useEffect(() => {
    activeBlockIndexRef.current = activeBlockIndex
  }, [activeBlockIndex])

  useEffect(() => {
    if (!currentTask) return

    setModelName(currentTask.formData.model_name)
    setCreateTime(currentTask.createdAt)
    if (activeBlockIndex === null) {
      setSelectedContent(currentTask.markdown)
    }
  }, [currentTask, taskStatus, activeBlockIndex])

  useEffect(() => {
    setActiveBlockIndex(null)
    setActiveBlockDraft('')
  }, [currentTask?.id])

  useEffect(() => {
    if (!currentTask?.id || status !== 'success') {
      setFavoriteId(null)
      return
    }

    let cancelled = false

    getFavoriteByTask(currentTask.id)
      .then(({ favorite }) => {
        if (cancelled) return
        setFavoriteId(favorite?.id ?? null)
      })
      .catch(error => {
        if (!cancelled) {
          console.warn('查询收藏状态失败', error)
          setFavoriteId(null)
        }
      })

    return () => {
      cancelled = true
    }
  }, [currentTask?.id, status])

  const handleToggleFavorite = async () => {
    if (!currentTask?.id) return

    setFavoritePending(true)
    try {
      if (favoriteId) {
        await deleteFavorite(favoriteId)
        setFavoriteId(null)
      } else {
        const { favorite } = await createFavorite(currentTask.id)
        setFavoriteId(favorite.id)
      }
    } finally {
      setFavoritePending(false)
    }
  }

  const persistMarkdown = async (nextMarkdown: string) => {
    if (!currentTask?.id) return
    if (!nextMarkdown.trim()) {
      toast.error('文字稿不能为空')
      return false
    }

    try {
      const { result } = await updateTaskMarkdown({
        task_id: currentTask.id,
        markdown: nextMarkdown,
      })
      const savedMarkdown = result?.markdown || nextMarkdown
      setSelectedContent(savedMarkdown)
      updateTaskContent(currentTask.id, { markdown: savedMarkdown })
      return true
    } catch {
      toast.error('保存文字稿失败')
      return false
    }
  }

  const buildMarkdownWithActiveDraft = () => {
    if (activeBlockIndex === null) return selectedContent

    return restoreSourceLink(
      selectedContent,
      joinMarkdownBlocks(replaceMarkdownBlock(markdownBlocks, activeBlockIndex, activeBlockDraft))
    )
  }

  const handlePreviewBlockClick = (event: MouseEvent<HTMLDivElement>, blockIndex: number) => {
    const target = event.target as HTMLElement
    if (target.closest('a,button,img')) return

    activeBlockIndexRef.current = blockIndex
    setActiveBlockIndex(blockIndex)
    setActiveBlockDraft(markdownBlocks[blockIndex] || '')
  }

  const handleBlockBlur = async () => {
    if (activeBlockIndex === null) return

    const editingBlockIndex = activeBlockIndex
    const nextMarkdown = buildMarkdownWithActiveDraft()
    if (nextMarkdown === selectedContent) {
      activeBlockIndexRef.current = null
      setActiveBlockIndex(null)
      setActiveBlockDraft('')
      return
    }

    setSavingBlockIndex(editingBlockIndex)
    const saved = await persistMarkdown(nextMarkdown)
    setSavingBlockIndex(null)
    if (saved && activeBlockIndexRef.current === editingBlockIndex) {
      activeBlockIndexRef.current = null
      setActiveBlockIndex(null)
      setActiveBlockDraft('')
    }
  }

  const handleBlockKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      activeBlockIndexRef.current = null
      setActiveBlockIndex(null)
      setActiveBlockDraft('')
      return
    }

    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      event.currentTarget.blur()
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildMarkdownWithActiveDraft())
      toast.success('已复制到剪贴板')
    } catch {
      toast.error('复制失败')
    }
  }
  const handleDownload = () => {
    const task = getSelectedTask()
    const name = task?.audioMeta.title || 'transcript'
    const blob = new Blob([buildMarkdownWithActiveDraft()], {
      type: 'text/markdown;charset=utf-8',
    })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${name}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  if (status === 'loading') {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center space-y-4 text-neutral-500">
        <StepBar steps={steps} currentStep={taskStatus} />
        <Loading />
        <div className="text-center text-sm">
          <p className="text-lg font-bold">正在生成文字稿，请稍候…</p>
          <p className="mt-2 text-xs text-neutral-500">这可能需要几秒钟时间，取决于视频长度</p>
        </div>
      </div>
    )
  }

  if (status === 'idle') {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center space-y-3 text-neutral-500">
        <Idle />
        <div className="text-center">
          <p className="text-lg font-bold">输入视频链接并点击"生成文字稿"</p>
          <p className="mt-2 text-xs text-neutral-500">支持哔哩哔哩、YouTube 、抖音等视频平台</p>
        </div>
      </div>
    )
  }

  if (status === 'failed') {
    const cancelled = taskStatus === 'CANCELLED'
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center gap-4 space-y-3">
        <Error />
        <div className="text-center">
          <p className="text-lg font-bold text-red-500">
            {cancelled ? '任务已取消' : '文字稿生成失败'}
          </p>
          <p className="mt-2 mb-2 text-xs text-red-400">
            {cancelled ? '这个任务已经停止，不会继续执行。' : '请检查后台或稍后再试'}
          </p>
          {!cancelled && currentTask ? (
            <Button
              onClick={() => {
                setCurrentTask(currentTask.id)
                retryTask(currentTask.id)
              }}
              size="lg"
            >
              重试
            </Button>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      <MarkdownHeader
        modelName={modelName}
        onCopy={handleCopy}
        onDownload={handleDownload}
        createAt={createTime}
        showTranscribe={showTranscribe}
        setShowTranscribe={setShowTranscribe}
        favoriteActive={favoriteId !== null}
        favoritePending={favoritePending}
        onToggleFavorite={status === 'success' ? handleToggleFavorite : undefined}
      />

      <div className="flex flex-1 overflow-hidden bg-white py-2">
        {selectedContent && selectedContent !== 'loading' && selectedContent !== 'empty' ? (
          <>
            <ScrollArea className="min-w-0 flex-1">
              <div className="px-2">
                <VideoBanner
                  audioMeta={currentTask?.audioMeta}
                  videoUrl={currentTask?.formData?.video_url}
                />
              </div>
              <div className="markdown-body w-full px-2">
                {markdownBlocks.map((block, blockIndex) =>
                  activeBlockIndex === blockIndex ? (
                    <Textarea
                      key={`editor-${blockIndex}`}
                      value={activeBlockDraft}
                      autoFocus
                      rows={Math.min(18, Math.max(3, activeBlockDraft.split('\n').length + 1))}
                      onBlur={handleBlockBlur}
                      onChange={event => setActiveBlockDraft(event.target.value)}
                      onKeyDown={handleBlockKeyDown}
                      disabled={savingBlockIndex === blockIndex}
                      className="my-3 resize-y whitespace-pre-wrap font-mono text-sm leading-6"
                      aria-label="编辑当前文字稿片段"
                    />
                  ) : (
                    <div
                      key={`preview-${blockIndex}`}
                      className="cursor-text rounded-md px-2 py-1 transition-colors hover:bg-neutral-50"
                      onClick={event => handlePreviewBlockClick(event, blockIndex)}
                    >
                      <ReactMarkdown
                        remarkPlugins={remarkPlugins}
                        rehypePlugins={rehypePlugins}
                        components={markdownComponents}
                      >
                        {block}
                      </ReactMarkdown>
                    </div>
                  )
                )}
              </div>
            </ScrollArea>
            {showTranscribe && (
              <div className={'ml-2 w-2/4'}>
                <TranscriptViewer />
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <div className="w-[300px] flex-col justify-items-center">
              <div className="bg-primary-light mb-4 flex h-16 w-16 items-center justify-center rounded-full">
                <ArrowRight className="text-primary h-8 w-8" />
              </div>
              <p className="mb-2 text-neutral-600">输入视频链接并点击"生成文字稿"按钮</p>
              <p className="text-xs text-neutral-500">支持哔哩哔哩、YouTube等视频网站</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

MarkdownViewer.displayName = 'MarkdownViewer'

export default MarkdownViewer
