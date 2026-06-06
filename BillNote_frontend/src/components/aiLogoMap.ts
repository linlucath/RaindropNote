import Claude from '@lobehub/icons/es/Claude'
import DeepSeek from '@lobehub/icons/es/DeepSeek'
import Gemini from '@lobehub/icons/es/Gemini'
import Groq from '@lobehub/icons/es/Groq'
import Ollama from '@lobehub/icons/es/Ollama'
import OpenAI from '@lobehub/icons/es/OpenAI'
import Qwen from '@lobehub/icons/es/Qwen'

type LogoVariant = React.ComponentType<{ size?: number }>
type LogoComponent = LogoVariant & Partial<Record<'Color' | 'Text' | 'Outlined' | 'Glyph', LogoVariant>>

export const aiLogoMap = {
  OpenAI,
  DeepSeek,
  Qwen,
  Claude,
  Gemini,
  Groq,
  Ollama,
} satisfies Record<string, LogoComponent>

export type AiLogoName = keyof typeof aiLogoMap
export type AiLogoStyle = 'Color' | 'Text' | 'Outlined' | 'Glyph'

export const getAiLogo = (name: string): LogoComponent | undefined =>
  aiLogoMap[name as AiLogoName]
