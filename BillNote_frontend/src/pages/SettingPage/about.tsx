import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import logo from '@/assets/icon.svg'

const features = [
  { title: '学习材料整理', desc: '将有权使用的视频、音频或本地文件整理成可阅读的文字稿。' },
  { title: 'AI 笔记生成', desc: '基于文字稿生成章节、重点、摘要和可继续编辑的 Markdown 笔记。' },
  { title: '原文参照', desc: '保留分段转写结果，便于核对、修订和追溯上下文。' },
  { title: '自定义模型', desc: '支持配置兼容的大模型服务和多种语音转写方案。' },
  { title: '历史管理', desc: '自动保留生成记录，方便回看、收藏和继续整理。' },
  { title: '本地优先', desc: '支持源码、Docker 和桌面端运行，适合个人工作流。' },
]

const boundaries = [
  '仅处理你拥有权利、获得授权，或平台规则允许用于个人学习和整理的内容。',
  '请勿用于绕过访问控制、会员限制、付费限制或其他技术保护措施。',
  '请勿批量抓取、复制、存储或传播第三方平台内容。',
  '生成结果可能包含识别错误或模型幻觉，正式引用前请自行核验。',
]

export default function AboutPage() {
  return (
    <ScrollArea className="h-full overflow-y-auto bg-white">
      <div className="container mx-auto px-4 py-12">
        <div className="mb-14 flex flex-col items-center justify-center text-center">
          <div className="mb-4 flex items-center gap-4">
            <img
              src={logo}
              alt="雨滴笔记助手 Logo"
              width={50}
              height={50}
              className="rounded-lg"
            />
            <h1 className="text-4xl font-bold">雨滴笔记助手</h1>
          </div>
          <p className="text-muted-foreground mb-6 max-w-3xl text-xl">
            面向个人学习、研究和内容整理场景的 AI 视频文字稿与笔记工具。
          </p>

          <div className="flex flex-wrap justify-center gap-2">
            <Badge variant="secondary">MIT License</Badge>
            <Badge variant="secondary">React</Badge>
            <Badge variant="secondary">FastAPI</Badge>
            <Badge variant="secondary">Docker</Badge>
            <Badge variant="secondary">Local First</Badge>
          </div>
        </div>

        <section className="mb-14">
          <h2 className="mb-5 text-center text-3xl font-bold">项目定位</h2>
          <p className="mx-auto max-w-3xl text-center text-lg leading-8">
            雨滴笔记助手关注的是把已经合法获得的学习材料整理成自己的知识资产。它不是下载器、
            搬运工具或内容分发服务，适合课程复盘、会议材料整理、公开讲座学习和本地音视频转写。
          </p>
        </section>

        <section className="mb-14">
          <h2 className="mb-8 text-center text-3xl font-bold">功能特性</h2>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {features.map(feature => (
              <Card key={feature.title} className="h-full">
                <CardContent className="pt-2">
                  <h3 className="mb-2 text-xl font-semibold">{feature.title}</h3>
                  <p className="text-muted-foreground leading-7">{feature.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="mb-14">
          <h2 className="mb-8 text-center text-3xl font-bold">使用边界</h2>
          <div className="mx-auto grid max-w-4xl grid-cols-1 gap-4 md:grid-cols-2">
            {boundaries.map(item => (
              <Card key={item}>
                <CardContent className="pt-2">
                  <p className="text-muted-foreground leading-7">{item}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="mb-14">
          <h2 className="mb-8 text-center text-3xl font-bold">快速开始</h2>
          <Tabs defaultValue="manual" className="mx-auto max-w-3xl">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="manual">源码运行</TabsTrigger>
              <TabsTrigger value="docker">Docker</TabsTrigger>
            </TabsList>
            <TabsContent value="manual" className="mt-6 space-y-6">
              <div>
                <h3 className="mb-3 text-xl font-semibold">1. 启动后端</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  cd backend
                  <br />
                  pip install -r requirements.txt
                  <br />
                  python main.py
                </div>
              </div>
              <div>
                <h3 className="mb-3 text-xl font-semibold">2. 启动前端</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  cd BillNote_frontend
                  <br />
                  pnpm install
                  <br />
                  pnpm dev
                </div>
              </div>
              <p>
                默认访问：<code className="bg-muted rounded px-2 py-1">http://localhost:3015</code>
              </p>
            </TabsContent>
            <TabsContent value="docker" className="mt-6 space-y-6">
              <div>
                <h3 className="mb-3 text-xl font-semibold">启动服务</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  docker-compose up
                  <br />
                  docker-compose -f docker-compose.gpu.yml up
                </div>
              </div>
              <p className="text-muted-foreground">
                Docker 入口端口由根目录 <code>.env</code> 中的 <code>APP_PORT</code> 控制。
              </p>
            </TabsContent>
          </Tabs>
        </section>

        <section className="text-center">
          <h2 className="mb-4 text-3xl font-bold">License</h2>
          <p>MIT License</p>
        </section>
      </div>
    </ScrollArea>
  )
}
