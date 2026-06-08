export const AUDIO_TRANSCRIPTION_REMOVED_MESSAGE = '当前仅支持平台字幕生成'

interface TaskPollingErrorResolutionInput {
  errorCode?: number
  message: string
}

interface TaskPollingErrorResolution {
  shouldMarkFailed: boolean
  failedMessage?: string
}

export const getTaskPollingErrorResolution = ({
  errorCode,
  message,
}: TaskPollingErrorResolutionInput): TaskPollingErrorResolution => {
  if (message.includes(AUDIO_TRANSCRIPTION_REMOVED_MESSAGE)) {
    return {
      shouldMarkFailed: true,
      failedMessage: message,
    }
  }

  if (errorCode !== undefined && errorCode !== -1) {
    return {
      shouldMarkFailed: true,
      failedMessage: message || '任务失败',
    }
  }

  return {
    shouldMarkFailed: false,
  }
}
