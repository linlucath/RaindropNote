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

test('followings mode preloads the first page and auto-loads uploader videos on selection', async ({
  page,
}) => {
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  let followingsRequestCount = 0
  let uploaderVideoRequestCount = 0

  page.on('pageerror', error => {
    pageErrors.push(error.message)
  })

  page.on('console', message => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text())
    }
  })

  await page.route('**/*', async route => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path.endsWith('/sys_check') || path.endsWith('/sys_health')) {
      await route.fulfill({ json: ok({}) })
      return
    }

    if (path.endsWith('/model_list')) {
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

    if (path.endsWith('/get_downloader_cookie/bilibili')) {
      await route.fulfill({
        json: ok({
          cookie: 'DedeUserID=123456;SESSDATA=test;',
          platform: 'bilibili',
        }),
      })
      return
    }

    if (path.endsWith('/bilibili/followings')) {
      followingsRequestCount += 1
      await route.fulfill({
        json: ok({
          items: [
            { mid: 'mid-1', name: '测试 UP 主一', sign: '简介一' },
            { mid: 'mid-2', name: '测试 UP 主二', sign: '简介二' },
          ],
          page: 1,
          page_size: 20,
          has_more: false,
          total: 2,
        }),
      })
      return
    }

    if (path.endsWith('/bilibili/uploader_videos')) {
      uploaderVideoRequestCount += 1
      await route.fulfill({
        json: ok({
          items: [
            {
              video_id: 'BV1followA',
              video_url: 'https://www.bilibili.com/video/BV1followA',
              title: '自动拉取的第一条视频',
              author_name: '测试 UP 主一',
            },
            {
              video_id: 'BV1followB',
              video_url: 'https://www.bilibili.com/video/BV1followB',
              title: '自动拉取的第二条视频',
              author_name: '测试 UP 主一',
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

    if (path.endsWith('/task_list')) {
      await route.fulfill({ json: ok({ tasks: [] }) })
      return
    }

    await route.continue()
  })

  await page.goto('/')

  await expect(page.getByText('BiliNote')).toBeVisible()

  await page.getByRole('button', { name: 'UP 主批量' }).click()
  await page.getByRole('button', { name: '从关注列表选择' }).click()

  await expect
    .poll(() => followingsRequestCount, {
      message: '进入关注模式后应已有且仅有一轮关注列表请求',
    })
    .toBe(1)
  await expect(page.getByText('测试 UP 主一')).toBeVisible()
  await page.getByText('测试 UP 主一').click()

  await expect
    .poll(() => uploaderVideoRequestCount, {
      message: '选中关注的 UP 主后应自动拉取第一页视频',
    })
    .toBe(1)

  await expect(page.getByText('视频标题预览')).toBeVisible()
  await expect(page.getByText('自动拉取的第一条视频')).toBeVisible()
  await expect(page.getByText('已选 0 / 2')).toBeVisible()

  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})
