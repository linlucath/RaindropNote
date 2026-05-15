export const AUDIO_TRANSCRIPTION_CONFIRMATION_MESSAGE = '需要确认音频转写'

interface TaskPollingErrorResolutionInput {
  errorCode?: number
  message: string
  allowAudioTranscription?: boolean
  audioTranscriptionConfirmed?: boolean
}

interface TaskPollingErrorResolution {
  shouldAskAudioTranscription: boolean
  shouldMarkFailed: boolean
}

export const getTaskPollingErrorResolution = ({
  errorCode,
  message,
  allowAudioTranscription = false,
  audioTranscriptionConfirmed,
}: TaskPollingErrorResolutionInput): TaskPollingErrorResolution => {
  const requiresAudioTranscriptionConfirmation =
    message.includes(AUDIO_TRANSCRIPTION_CONFIRMATION_MESSAGE) && !allowAudioTranscription

  if (requiresAudioTranscriptionConfirmation) {
    if (audioTranscriptionConfirmed === false) {
      return {
        shouldAskAudioTranscription: false,
        shouldMarkFailed: true,
      }
    }

    return {
      shouldAskAudioTranscription: true,
      shouldMarkFailed: false,
    }
  }

  return {
    shouldAskAudioTranscription: false,
    shouldMarkFailed: errorCode !== undefined && errorCode !== -1,
  }
}
