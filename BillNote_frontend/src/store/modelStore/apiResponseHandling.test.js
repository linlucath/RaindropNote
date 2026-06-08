import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('./index.ts', import.meta.url),
  'utf8'
)

test('model store does not treat request helper results as wrapped responses', () => {
  assert.doesNotMatch(source, /res\.code\s*===\s*0/)
  assert.doesNotMatch(source, /res\.data\.code\s*===\s*0/)
})

test('model store refreshes enabled models through the zustand get accessor after adding a model', () => {
  assert.match(source, /devtools\(\(\s*set\s*,\s*get\s*\)/)
  assert.match(source, /await get\(\)\.loadEnabledModels\(\)/)
})
