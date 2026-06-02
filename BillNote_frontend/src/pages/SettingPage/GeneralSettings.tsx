import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  DEFAULT_GENERATION_QUALITY,
  GenerationQuality,
  getPreferredDefaultModelName,
  useGenerationSettingsStore,
} from '@/store/generationSettingsStore'
import { useModelStore } from '@/store/modelStore'

const qualityOptions: Array<{ value: GenerationQuality; label: string; description: string }> = [
  { value: 'fast', label: '快速', description: '优先速度，适合快速浏览文字稿。' },
  { value: 'medium', label: '均衡', description: '兼顾处理速度与结果质量。' },
  { value: 'slow', label: '精细', description: '优先结果质量，处理耗时更长。' },
]

export default function GeneralSettings() {
  const { loadEnabledModels, modelList } = useModelStore()
  const modelName = useGenerationSettingsStore(state => state.model_name)
  const quality = useGenerationSettingsStore(state => state.quality)
  const setGenerationSettings = useGenerationSettingsStore(state => state.setGenerationSettings)

  const preferredDefaultModelName = useMemo(
    () => getPreferredDefaultModelName(modelList),
    [modelList]
  )

  useEffect(() => {
    loadEnabledModels()
  }, [loadEnabledModels])

  useEffect(() => {
    if (!preferredDefaultModelName) {
      return
    }

    if (!modelName) {
      setGenerationSettings({ model_name: preferredDefaultModelName })
      return
    }

    const modelStillExists = modelList.some(model => model.model_name === modelName)
    if (!modelStillExists) {
      setGenerationSettings({ model_name: preferredDefaultModelName })
    }
  }, [modelList, modelName, preferredDefaultModelName, setGenerationSettings])

  return (
    <ScrollArea className="h-full overflow-y-auto bg-white">
      <div className="container mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">全局配置</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            这些生成设置会应用到所有新任务，首页不再为每个任务单独展示。
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>生成设置</CardTitle>
            <CardDescription>设置默认模型和默认处理速度。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label>默认模型</Label>
              {modelList.length > 0 ? (
                <Select
                  value={modelName || preferredDefaultModelName}
                  onOpenChange={open => {
                    if (open) {
                      loadEnabledModels()
                    }
                  }}
                  onValueChange={value => setGenerationSettings({ model_name: value })}
                >
                  <SelectTrigger className="w-full min-w-0 truncate">
                    <SelectValue placeholder="请选择模型" />
                  </SelectTrigger>
                  <SelectContent>
                    {modelList.map(model => (
                      <SelectItem key={model.id} value={model.model_name}>
                        {model.model_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Button asChild variant="outline" className="w-full">
                  <Link to="/settings/model">请先添加模型</Link>
                </Button>
              )}
              <p className="text-muted-foreground text-xs">
                默认优先选择 DeepSeek 模型；你也可以在这里手动固定。
              </p>
            </div>

            <div className="space-y-2">
              <Label>默认处理速度</Label>
              <Select
                value={quality || DEFAULT_GENERATION_QUALITY}
                onValueChange={value =>
                  setGenerationSettings({ quality: value as GenerationQuality })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {qualityOptions.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-xs">
                {qualityOptions.find(option => option.value === quality)?.description ||
                  qualityOptions.find(option => option.value === DEFAULT_GENERATION_QUALITY)
                    ?.description}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  )
}
