import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const source = readFileSync(path.join(__dirname, 'NoteForm.tsx'), 'utf8')

test('NoteForm prefers a DeepSeek model as the default selection', () => {
  assert.match(source, /const DEFAULT_QUALITY = 'medium'/)
  assert.match(source, /models\.find\(model => model\.provider_id === 'deepseek'\)\?\.model_name/)
  assert.match(
    source,
    /models\.find\(model => model\.model_name\.toLowerCase\(\)\.includes\('deepseek'\)\)\?\.model_name/
  )
})

test('NoteForm reapplies the preferred default model after model list loading and reset', () => {
  assert.match(source, /if \(!currentModelName\) {\s+form\.setValue\('model_name', preferredDefaultModelName/)
  assert.match(source, /model_name: formData\.model_name \|\| preferredDefaultModelName/)
  assert.match(source, /model_name: preferredDefaultModelName/)
})
