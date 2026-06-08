import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('./index.ts', import.meta.url),
  'utf8'
)

test('provider store does not treat request helper results as wrapped responses', () => {
  assert.doesNotMatch(source, /res\.data\.code\s*===\s*0/)
})
