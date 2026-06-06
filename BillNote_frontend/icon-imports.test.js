import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

test('AI logo components use explicit icon mapping instead of whole-package imports', () => {
  const files = [
    'src/components/aiLogoMap.ts',
    'src/components/Icons/index.tsx',
    'src/components/Form/modelForm/Icons/index.tsx',
  ]

  for (const file of files) {
    const source = readFileSync(join(__dirname, file), 'utf8')
    assert.doesNotMatch(source, /import\s+\*\s+as\s+Icons\s+from\s+['"]@lobehub\/icons['"]/)
  }

  const mapSource = readFileSync(join(__dirname, 'src/components/aiLogoMap.ts'), 'utf8')
  for (const iconName of ['OpenAI', 'DeepSeek', 'Qwen', 'Claude', 'Gemini', 'Groq', 'Ollama']) {
    assert.match(mapSource, new RegExp(`\\b${iconName},`))
    assert.match(mapSource, new RegExp(`@lobehub/icons/es/${iconName}`))
  }
})

test('custom fallback logo uses a small icon asset instead of the original large PNG', () => {
  const source = readFileSync(
    join(__dirname, 'src/components/Form/modelForm/Icons/index.tsx'),
    'utf8'
  )

  assert.doesNotMatch(source, /@\/assets\/customAI\.png/)
  assert.match(source, /@\/assets\/customAI-icon\.png/)
})
