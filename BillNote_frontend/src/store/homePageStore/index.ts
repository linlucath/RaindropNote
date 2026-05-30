import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  buildPersistedHomePageState,
  createDefaultHomePageFormState,
  createEmptyHomePagePreviewState,
  type HomePageFormState,
  type HomePagePreviewState,
} from './persistHomePageState.ts'

interface HomePageStore {
  form: HomePageFormState
  preview: HomePagePreviewState
  setFormState: (next: Partial<HomePageFormState>) => void
  replaceFormState: (next: HomePageFormState) => void
  setPreviewState: (next: Partial<HomePagePreviewState>) => void
  replacePreviewState: (next: HomePagePreviewState) => void
  clearPreviewState: () => void
  resetHomePageState: (defaultModelName?: string) => void
}

export const useHomePageStore = create<HomePageStore>()(
  persist(
    set => ({
      form: createDefaultHomePageFormState(),
      preview: createEmptyHomePagePreviewState(),
      setFormState: next =>
        set(state => ({
          form: {
            ...state.form,
            ...next,
          },
        })),
      replaceFormState: next =>
        set({
          form: { ...next },
        }),
      setPreviewState: next =>
        set(state => ({
          preview: {
            ...state.preview,
            ...next,
          },
        })),
      replacePreviewState: next =>
        set({
          preview: {
            ...next,
            videos: [...next.videos],
            selectedUploader: next.selectedUploader ? { ...next.selectedUploader } : null,
          },
        }),
      clearPreviewState: () =>
        set({
          preview: createEmptyHomePagePreviewState(),
        }),
      resetHomePageState: defaultModelName =>
        set({
          form: createDefaultHomePageFormState(defaultModelName),
          preview: createEmptyHomePagePreviewState(),
        }),
    }),
    {
      name: 'home-page-store',
      partialize: state => buildPersistedHomePageState(state),
    }
  )
)
