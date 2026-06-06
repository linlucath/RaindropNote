import { getAiLogo, type AiLogoStyle } from '@/components/aiLogoMap'
import CustomLogo from '@/assets/customAI-icon.png'

interface AILogoProps {
  name: string // 图标名称（区分大小写！如 OpenAI、DeepSeek）
  style?: AiLogoStyle
  size?: number
}

const AILogo = ({ name, style = 'Color', size = 24 }: AILogoProps) => {
  const Icon = getAiLogo(name)
  if (!Icon) {
    console.error(`❌ 图标组件不存在: ${name}`)
    return (
      <span style={{ fontSize: size }}>
        <img src={CustomLogo} alt="CustomLogo" style={{ width: size, height: size }} />
      </span>
    )
  }

  const Variant = Icon[style]
  if (!Variant) {
    return <Icon size={size} />
  }

  return <Variant size={size} />
}

export default AILogo
