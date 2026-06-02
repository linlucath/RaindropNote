import { useTaskStore } from '@/store/taskStore'
import { cn } from '@/lib/utils.ts'
import { Trash } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import Fuse from 'fuse.js'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { FC, useEffect, useMemo, useState } from 'react'
import { get_task_list } from '@/services/note.ts'

interface NoteHistoryProps {
  onSelect: (taskId: string) => void
  selectedId: string | null
}

const NoteHistory: FC<NoteHistoryProps> = ({ onSelect, selectedId }) => {
  const tasks = useTaskStore(state => state.tasks)
  const removeTask = useTaskStore(state => state.removeTask)
  const syncSavedTasks = useTaskStore(state => state.syncSavedTasks)
  const [search, setSearch] = useState('')

  useEffect(() => {
    get_task_list()
      .then(res => syncSavedTasks(res?.tasks || []))
      .catch(error => console.warn('同步历史任务失败', error))
  }, [syncSavedTasks])

  const fuse = useMemo(
    () =>
      new Fuse(tasks, {
        keys: ['audioMeta.title'],
        threshold: 0.4, // 匹配精度（越低越严格）
      }),
    [tasks]
  )
  const filteredTasks = search.trim()
    ? fuse.search(search).map(result => result.item)
    : tasks
  if (filteredTasks.length === 0) {
    return (
      <>
        <div className="mb-2">
          <input
            type="text"
            placeholder="搜索文字稿标题..."
            className="w-full rounded border border-neutral-300 px-3 py-1 text-sm outline-none focus:border-primary"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="rounded-md border border-neutral-200 bg-neutral-50 py-6 text-center">
          <p className="text-sm text-neutral-500">暂无记录</p>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="mb-2">
        <input
          type="text"
          placeholder="搜索文字稿标题..."
          className="w-full rounded border border-neutral-300 px-3 py-1 text-sm outline-none focus:border-primary"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2 overflow-hidden">
        {filteredTasks.map(task => (
          <div
            key={task.id}
            onClick={() => onSelect(task.id)}
            className={cn(
              'flex cursor-pointer flex-col rounded-md border border-neutral-200 p-3',
              selectedId === task.id && 'border-primary bg-primary-light'
            )}
          >
            <div className={cn('flex items-center gap-4')}>
              <div className="flex w-full items-center justify-between gap-2">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="line-clamp-2 max-w-[180px] flex-1 overflow-hidden text-sm text-ellipsis">
                        {task.audioMeta.title || '未命名文字稿'}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{task.audioMeta.title || '未命名文字稿'}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </div>
            <div className={'mt-2 flex items-center justify-between text-[10px]'}>
              <div className="shrink-0">
                {task.status === 'CANCELLED' && (
                  <div className={'inline-block w-10 rounded bg-neutral-500 p-0.5 text-center text-white'}>
                    已取消
                  </div>
                )}
                {task.status !== 'SUCCESS' && task.status !== 'FAILED' && task.status !== 'CANCELLED' ? (
                  <div className={'inline-block w-10 rounded bg-green-500 p-0.5 text-center text-white'}>
                    等待中
                  </div>
                ) : (
                  <></>
                )}
                {task.status === 'FAILED' && (
                  <div className={'inline-block w-10 rounded bg-red-500 p-0.5 text-center text-white'}>失败</div>
                )}
              </div>

              <div>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        size="small"
                        variant="ghost"
                        onClick={e => {
                          e.stopPropagation()
                          removeTask(task.id)
                        }}
                        className="shrink-0"
                      >
                        <Trash className="text-muted-foreground h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>删除</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

export default NoteHistory
