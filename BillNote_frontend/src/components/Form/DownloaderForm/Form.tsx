// 下载器 Cookie 设置表单（最简化版）
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from '@/components/ui/form'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  getDownloaderCookie,
  importDownloaderCookie,
  updateDownloaderCookie,
} from '@/services/downloader' // 你自定义的请求
import { useParams } from 'react-router-dom'
import { videoPlatforms } from '@/constant/note.ts'

const CookieSchema = z.object({
  cookie: z.string().min(10, '请填写有效 Cookie'),
})

const DownloaderForm = () => {
  const form = useForm({
    resolver: zodResolver(CookieSchema),
    defaultValues: { cookie: '' },
  })
  const { id } = useParams()

  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)

  useEffect(() => {
    const loadCookie = async () => {
      setLoading(true) // 🔁 切换平台时显示 loading
      try {
        const res = await getDownloaderCookie(id)
        const cookie = res?.cookie || ''
        form.reset({ cookie }) // ✅ 正确重置表单值
      } catch (error) {
        toast.error('加载 Cookie 失败: ' + String(error))
        form.reset({ cookie: '' }) // ❗失败时也要清空旧值
      } finally {
        setLoading(false)
      }
    }

    if (id) loadCookie()
  }, [form, id]) // 🔁 每当 id 变化时触发

  const onSubmit = async values => {
    try {
      await updateDownloaderCookie({
        platform: id,
        cookie: String(values.cookie),
      })
      toast.success('保存成功')
    } catch {
      toast.error('保存失败')
    }
  }

  const onImportCookie = async () => {
    if (id !== 'bilibili') return
    try {
      setImporting(true)
      const res = await importDownloaderCookie(id)
      const cookie = res?.cookie || ''
      form.reset({ cookie })
      toast.success('获取成功')
    } catch {
      toast.error('获取失败')
    } finally {
      setImporting(false)
    }
  }

  if (loading) return <div className="p-4">加载中...</div>

  return (
    <div className="max-w-xl p-4">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="text-lg font-bold">
            设置{videoPlatforms.find(item => item.value === id)?.label}下载器 Cookie
          </div>

          {id === 'bilibili' ? (
            <Button type="button" variant="outline" onClick={onImportCookie} disabled={importing}>
              {importing ? '获取中...' : '从浏览器获取'}
            </Button>
          ) : null}

          <FormField
            control={form.control}
            name="cookie"
            render={({ field }) => (
              <FormItem className="flex flex-col gap-2">
                <FormLabel>Cookie</FormLabel>
                <FormControl>
                  <Textarea {...field} className="min-h-40 font-mono text-sm" placeholder="输入 Cookie" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit">保存</Button>
        </form>
      </Form>
    </div>
  )
}

export default DownloaderForm
