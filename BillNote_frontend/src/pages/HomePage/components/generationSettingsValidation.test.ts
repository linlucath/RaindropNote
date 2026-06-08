import test from 'node:test'
import assert from 'node:assert/strict'

import { hasValidGenerationPayloadSettings } from './taskSubmission.ts'

test('requires both model name and provider id for transcript generation payloads', () => {
  assert.equal(hasValidGenerationPayloadSettings(null), false)
  assert.equal(
    hasValidGenerationPayloadSettings({
      model_name: 'deepseek-chat',
      provider_id: '',
    }),
    false
  )
  assert.equal(
    hasValidGenerationPayloadSettings({
      model_name: '',
      provider_id: 'deepseek',
    }),
    false
  )
  assert.equal(
    hasValidGenerationPayloadSettings({
      model_name: 'deepseek-chat',
      provider_id: 'deepseek',
    }),
    true
  )
})
