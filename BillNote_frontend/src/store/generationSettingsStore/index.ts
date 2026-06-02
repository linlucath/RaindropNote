import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type GenerationQuality = 'fast' | 'medium' | 'slow'

export interface GenerationSettings {
  model_name: string
  quality: GenerationQuality
}

interface GenerationSettingsStore extends GenerationSettings {
  setModelName: (modelName: string) => void
  setQuality: (quality: GenerationQuality) => void
  setGenerationSettings: (settings: Partial<GenerationSettings>) => void
  resetGenerationSettings: (modelName?: string) => void
}

export const DEFAULT_GENERATION_QUALITY: GenerationQuality = 'medium'

export const getPreferredDefaultModelName = (
  models: Array<{ model_name: string; provider_id: string }>
) => {
  if (!models.length) {
    return ''
  }

  return (
    models.find(model => model.provider_id === 'deepseek')?.model_name ||
    models.find(model => model.model_name.toLowerCase().includes('deepseek'))?.model_name ||
    models[0]?.model_name ||
    ''
  )
}

export function createDefaultGenerationSettings(modelName = ''): GenerationSettings {
  return {
    model_name: modelName,
    quality: DEFAULT_GENERATION_QUALITY,
  }
}

export const useGenerationSettingsStore = create<GenerationSettingsStore>()(
  persist(
    set => ({
      ...createDefaultGenerationSettings(),
      setModelName: model_name => set({ model_name }),
      setQuality: quality => set({ quality }),
      setGenerationSettings: settings => set(state => ({ ...state, ...settings })),
      resetGenerationSettings: modelName =>
        set({
          ...createDefaultGenerationSettings(modelName),
        }),
    }),
    {
      name: 'generation-settings-store',
    }
  )
)
