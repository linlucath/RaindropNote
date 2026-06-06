import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const viteConfig = readFileSync(join(__dirname, 'vite.config.ts'), 'utf8')

test('vite manual chunks keep heavy dependencies out of route chunks', () => {
  assert.match(viteConfig, /manualChunks:\s*\{/)

  const expectedChunks = {
    vendor: ['react', 'react-dom', 'react-router-dom'],
    design: ['antd', '@lobehub/icons', 'lucide-react'],
    markdown: ['react-markdown', 'react-syntax-highlighter', 'rehype-katex'],
    lottie: ['lottie-react'],
  }

  for (const [chunkName, packages] of Object.entries(expectedChunks)) {
    assert.match(viteConfig, new RegExp(`${chunkName}:\\s*\\[`))
    for (const packageName of packages) {
      assert.match(viteConfig, new RegExp(`['"]${packageName.replace('/', '\\/')}['"]`))
    }
  }
})

test('vite resolves lottie-react to the light lottie-web player without eval support', () => {
  assert.match(viteConfig, /['"]lottie-web['"]:\s*['"]lottie-web\/build\/player\/lottie_light['"]/)
})
