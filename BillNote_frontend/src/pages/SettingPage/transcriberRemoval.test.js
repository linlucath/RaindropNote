import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const menuSource = readFileSync(path.join(__dirname, 'Menu.tsx'), 'utf8')
const appSource = readFileSync(path.join(__dirname, '../../App.tsx'), 'utf8')

test('settings menu no longer exposes the transcriber configuration entry', () => {
  assert.doesNotMatch(menuSource, /id: 'transcriber'/)
  assert.doesNotMatch(menuSource, /音频转写配置/)
})

test('application routes no longer register the transcriber settings page', () => {
  assert.doesNotMatch(appSource, /TranscriberPage/)
  assert.doesNotMatch(appSource, /path="transcriber"/)
})
