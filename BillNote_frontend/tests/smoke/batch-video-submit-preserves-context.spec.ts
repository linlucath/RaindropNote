import { expect, test } from '@playwright/test'

type ApiEnvelope<T> = {
  code: number
  msg: string
  data: T
}

const ok = <T>(data: T): ApiEnvelope<T> => ({
  code: 0,
  msg: 'ok',
  data,
})

test('batch preview submission keeps the current batch context visible', async ({ page }) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []

  page.on('pageerror', error => {
    pageErrors.push(error.message)
  })

  page.on('console', message => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text())
    }
  })

  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())

    if (url.pathname.endsWith('/api/sys_check') || url.pathname.endsWith('/api/sys_health')) {
      await route.fulfill({ json: ok({}) })
      return
    }

    if (url.pathname.endsWith('/api/model_list')) {
      await route.fulfill({
        json: ok([
          {
            id: 'model-1',
            provider_id: 'provider-1',
            model_name: 'test-model',
          },
        ]),
      })
      return
    }

    if (url.pathname.endsWith('/api/batch/preview')) {
      await route.fulfill({
        json: ok({
          items: [
            {
              video_id: 'video-1',
              video_url: 'https://www.bilibili.com/video/BV1',
              title: '第一条视频',
            },
            {
              video_id: 'video-2',
              video_url: 'https://www.bilibili.com/video/BV2',
              title: '第二条视频',
            },
          ],
          page: 1,
          page_size: 20,
          has_more: false,
          total: 2,
        }),
      })
      return
    }

    if (url.pathname.endsWith('/api/generate_note')) {
      await route.fulfill({
        json: ok({
          task_id: 'task-preview-submit-1',
        }),
      })
      return
    }

    if (url.pathname.includes('/api/task_status/')) {
      await route.fulfill({
        json: ok({
          status: 'PENDING',
          result: {},
        }),
      })
      return
    }

    if (url.pathname.endsWith('/api/task_list')) {
      await route.fulfill({ json: ok({ tasks: [] }) })
      return
    }

    await route.fulfill({ json: ok({}) })
  })

  await page.goto('/')

  await expect(page.getByText('BiliNote')).toBeVisible()
  await page.getByRole('button', { name: 'UP 主批量' }).click()
  await page
    .getByPlaceholder('https://space.bilibili.com/123456')
    .fill('https://space.bilibili.com/123456')
  await page.getByRole('button', { name: '拉取' }).click()

  await expect(page.getByText('视频标题预览')).toBeVisible()
  await expect(page.getByText('第一条视频')).toBeVisible()

  await page.getByText('第一条视频').click()

  await expect(page.getByText('正在生成文字稿，请稍候…')).toBeVisible()
  await expect(page.getByText('视频标题预览')).toBeVisible()
  await expect(page.getByText('第一条视频')).toBeVisible()
  await expect(page.getByText('第二条视频')).toBeVisible()

  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})
