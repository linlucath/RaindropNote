import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

const removedDependencies = [
  '@ant-design/x',
  '@lobehub/icons-static-svg',
  '@lottiefiles/dotlottie-react',
  '@uiw/react-markdown-preview',
  'jszip',
  'markdown-navbar',
  'markmap-common',
  'markmap-lib',
  'markmap-toolbar',
  'markmap-view',
  'pinyin-match',
]

test('removed feature dependencies stay out of frontend manifests and build chunks', () => {
  const packageJson = JSON.parse(readFileSync(join(__dirname, 'package.json'), 'utf8'))
  const viteConfig = readFileSync(join(__dirname, 'vite.config.ts'), 'utf8')

  for (const dependency of removedDependencies) {
    assert.equal(packageJson.dependencies[dependency], undefined, dependency)
    assert.doesNotMatch(viteConfig, new RegExp(dependency.replaceAll('/', '\\/')))
  }
})
