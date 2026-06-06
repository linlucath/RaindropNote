import type { ReactNode, FC } from 'react'
// import "@/global.css"
import { Toaster } from 'react-hot-toast'

interface RootLayoutProps {
  children: ReactNode
}

export const metadata = {
  title: '雨滴笔记助手 - AI 学习笔记整理工具',
  description: '将有权使用的视频、音频或本地文件整理为文字稿与结构化笔记',
}

const RootLayout: FC<RootLayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-neutral-100 font-sans text-neutral-900">
      <Toaster
        position="top-center" // 顶部居中显示
        toastOptions={{
          style: {
            borderRadius: '8px',
            background: '#333',
            color: '#fff',
          },
        }}
      />
      {children}
    </div>
  )
}

export default RootLayout
