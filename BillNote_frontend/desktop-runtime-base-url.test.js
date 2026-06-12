import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const runtimeBaseUrlSource = readFileSync(
  join(__dirname, 'src/utils/runtimeBaseUrl.ts'),
  'utf8'
)
const requestSource = readFileSync(join(__dirname, 'src/utils/request.ts'), 'utf8')
const markdownViewerSource = readFileSync(
  join(__dirname, 'src/pages/HomePage/components/MarkdownViewer.tsx'),
  'utf8'
)
const viteConfigSource = readFileSync(join(__dirname, 'vite.config.ts'), 'utf8')

test('desktop builds route API requests to the local backend instead of relying on Vite proxy', () => {
  assert.match(runtimeBaseUrlSource, /MODE/)
  assert.match(runtimeBaseUrlSource, /DESKTOP_BUILD_MODE = 'tauri'/)
  assert.match(
    runtimeBaseUrlSource,
    /http:\/\/\$\{DESKTOP_BACKEND_HOST\}:\$\{DESKTOP_BACKEND_PORT\}\/api/
  )
  assert.match(requestSource, /runtimeApiBaseUrl/)
})

test('desktop markdown image URLs resolve against the local backend host', () => {
  assert.match(runtimeBaseUrlSource, /VITE_SCREENSHOT_BASE_URL/)
  assert.match(markdownViewerSource, /runtimeStaticBaseUrl/)
})

test('vite injects the backend port for desktop runtime URL resolution', () => {
  assert.match(viteConfigSource, /__DESKTOP_BACKEND_PORT__/)
  assert.match(viteConfigSource, /env\.BACKEND_PORT \|\| '8483'/)
})
