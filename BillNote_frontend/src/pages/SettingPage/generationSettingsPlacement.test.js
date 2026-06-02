import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const appSource = readFileSync(path.join(__dirname, '../../App.tsx'), 'utf8')
const menuSource = readFileSync(path.join(__dirname, 'Menu.tsx'), 'utf8')
const noteFormSource = readFileSync(
  path.join(__dirname, '../HomePage/components/NoteForm.tsx'),
  'utf8'
)

test('generation settings live under the global settings page', () => {
  assert.match(menuSource, /name: '全局配置'/)
  assert.match(menuSource, /path: '\/settings\/general'/)
  assert.match(appSource, /const GeneralSettings = lazy/)
  assert.match(appSource, /<Route path="general" element=\{<GeneralSettings \/>\}/)
})

test('home task form does not render per-task generation settings', () => {
  assert.doesNotMatch(noteFormSource, /WorkspaceSection title=\{batchMode \? '3\. 生成设置' : '生成设置'\}/)
  assert.doesNotMatch(noteFormSource, /<FormLabel>模型<\/FormLabel>/)
  assert.doesNotMatch(noteFormSource, /<FormLabel>处理速度<\/FormLabel>/)
})
