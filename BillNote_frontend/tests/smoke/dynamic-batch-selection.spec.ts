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

test('top-level dynamics source supports pagination and selection without runtime errors', async ({
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

    if (url.pathname.endsWith('/api/bilibili/dynamics')) {
      const offset = url.searchParams.get('offset')
      await route.fulfill({
        json: ok(
          !offset
            ? {
                items: [
                  {
                    video_id: 'BV1dynamicA',
                    video_url: 'https://www.bilibili.com/video/BV1dynamicA',
                    title: '第一条动态视频',
                    author_name: '作者甲',
                  },
                  {
                    video_id: 'BV1dynamicB',
                    video_url: 'https://www.bilibili.com/video/BV1dynamicB',
                    title: '第二条动态视频',
                    author_name: '作者乙',
                  },
                ],
                has_more: true,
                offset: 'dynamic-cursor-1',
                page_size: 2,
              }
            : {
                items: [
                  {
                    video_id: 'BV1dynamicC',
                    video_url: 'https://www.bilibili.com/video/BV1dynamicC',
                    title: '第三条动态视频',
                    author_name: '作者丙',
                  },
                ],
                has_more: false,
                offset: '',
                page_size: 1,
              }
        ),
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
  await page.getByRole('button', { name: '关注动态' }).click()
  await page.getByRole('button', { name: '拉取关注动态' }).click()

  await expect(page.getByText('视频标题预览')).toBeVisible()
  await expect(page.getByText('已选 0 / 2')).toBeVisible()
  await expect(page.getByText('第一条动态视频')).toBeVisible()
  await expect(page.getByText('作者甲')).toBeVisible()

  await page.getByText('第一条动态视频').click()
  await page.getByText('第二条动态视频').click()
  await expect(page.getByText('已选 2 / 2')).toBeVisible()

  await page.getByRole('button', { name: '加载更多' }).click()
  await expect(page.getByText('第三条动态视频')).toBeVisible()
  await expect(page.getByText('已选 2 / 3')).toBeVisible()

  await page.getByRole('button', { name: '全不选' }).click()
  await expect(page.getByText('已选 0 / 3')).toBeVisible()

  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})
