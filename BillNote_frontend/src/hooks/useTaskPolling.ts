import { useEffect, useRef } from 'react'
import { useTaskStore } from '@/store/taskStore'
import { generateNote, get_task_status, TERMINAL_TASK_STATUSES } from '@/services/note.ts'
import toast from 'react-hot-toast'
import { getTaskPollingErrorResolution } from './taskPollingErrorHandling.ts'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)

  const tasksRef = useRef(tasks)

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => !TERMINAL_TASK_STATUSES.includes(task.status as (typeof TERMINAL_TASK_STATUSES)[number])
      )

      // 无活跃任务时跳过轮询
      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          const { status } = res

          if (status && status !== task.status) {
            if (status === 'SUCCESS') {
              const { markdown, transcript, audio_meta } = res.result
              toast.success('文字稿生成成功')
              updateTaskContent(task.id, {
                status,
                markdown,
                transcript,
                audioMeta: audio_meta,
              })
            } else if (status === 'FAILED') {
              updateTaskContent(task.id, { status })
              console.warn(`⚠️ 任务 ${task.id} 失败`)
            } else if (status === 'CANCELLED') {
              updateTaskContent(task.id, { status })
            } else {
              updateTaskContent(task.id, { status })
            }
          }
        } catch (e: unknown) {
          console.error('❌ 任务轮询失败：', e)
          const message =
            typeof e === 'object' && e
              ? String(('msg' in e && e.msg) || ('message' in e && e.message) || '')
              : ''
          const errorCode =
            typeof e === 'object' && e && 'code' in e && typeof e.code === 'number'
              ? e.code
              : undefined
          const initialResolution = getTaskPollingErrorResolution({
            errorCode,
            message,
            allowAudioTranscription: task.formData?.allow_audio_transcription,
          })

          if (initialResolution.shouldAskAudioTranscription) {
            const confirmed = window.confirm(
              '没有找到可用字幕文件。是否允许下载音频并进行转写？'
            )
            const resolution = getTaskPollingErrorResolution({
              errorCode,
              message,
              allowAudioTranscription: task.formData?.allow_audio_transcription,
              audioTranscriptionConfirmed: confirmed,
            })

            if (confirmed) {
              const formData = {
                ...task.formData,
                allow_audio_transcription: true,
              }
              await generateNote({
                ...formData,
                task_id: task.id,
              })
              updateTaskContent(task.id, {
                status: 'PENDING',
                formData,
              })
              continue
            }

            if (resolution.shouldMarkFailed) {
              updateTaskContent(task.id, { status: 'FAILED' })
              continue
            }
          }

          if (initialResolution.shouldMarkFailed) {
            updateTaskContent(task.id, { status: 'FAILED' })
          }
          // Keep polling on transient request errors. A task should only become FAILED
          // when the backend explicitly reports FAILED, not when one poll request flakes.
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval, updateTaskContent])
}
