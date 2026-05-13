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

test('manual uploader batch selection can be cleared without runtime errors', async ({
  page,
}) => {
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
            {
              video_id: 'video-3',
              video_url: 'https://www.bilibili.com/video/BV3',
              title: '第三条视频',
            },
          ],
          page: 1,
          page_size: 20,
          has_more: false,
          total: 3,
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
  await expect(page.getByText('已选 0 / 3')).toBeVisible()

  await page.getByText('第一条视频').click()
  await page.getByText('第二条视频').click()

  await expect(page.getByText('已选 2 / 3')).toBeVisible()
  await page.getByRole('button', { name: '全不选' }).click()
  await expect(page.getByText('已选 0 / 3')).toBeVisible()

  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})
