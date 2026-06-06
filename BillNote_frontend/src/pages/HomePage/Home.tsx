import { FC, lazy, Suspense, useEffect, useState } from 'react'
import HomeLayout from '@/layouts/HomeLayout.tsx'
import { useTaskStore } from '@/store/taskStore'

const NoteForm = lazy(() => import('@/pages/HomePage/components/NoteForm.tsx'))
const MarkdownViewer = lazy(() => import('@/pages/HomePage/components/MarkdownViewer.tsx'))
const History = lazy(() => import('@/pages/HomePage/components/History.tsx'))

type ViewStatus = 'idle' | 'loading' | 'success' | 'failed'
export const HomePage: FC = () => {
  const tasks = useTaskStore(state => state.tasks)
  const selectedTaskId = useTaskStore(state => state.selectedTaskId)

  const currentTask = tasks.find(t => t.id === (selectedTaskId ?? null))

  const [status, setStatus] = useState<ViewStatus>('idle')

  useEffect(() => {
    if (!currentTask) {
      setStatus('idle')
    } else if (currentTask.status === 'SUCCESS') {
      setStatus('success')
    } else if (currentTask.status === 'FAILED' || currentTask.status === 'CANCELLED') {
      setStatus('failed')
    } else {
      // PENDING、PARSING、DOWNLOADING、TRANSCRIBING、SUMMARIZING 等所有进行中状态
      setStatus('loading')
    }
  }, [currentTask, currentTask?.status])

  // useEffect( () => {
  //     get_task_status('d4e87938-c066-48a0-bbd5-9bec40d53354').then(res=>{
  //         console.log('res1',res)
  //         setContent(res.data.result.markdown)
  //     })
  // }, [tasks]);
  return (
    <HomeLayout
      NoteForm={
        <Suspense fallback={null}>
          <NoteForm />
        </Suspense>
      }
      Preview={
        <Suspense fallback={null}>
          <MarkdownViewer status={status} />
        </Suspense>
      }
      History={
        <Suspense fallback={null}>
          <History />
        </Suspense>
      }
    />
  )
}
