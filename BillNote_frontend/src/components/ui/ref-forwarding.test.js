import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const componentFiles = ['input.tsx', 'textarea.tsx', 'label.tsx', 'switch.tsx', 'checkbox.tsx']

for (const fileName of componentFiles) {
  test(`${fileName} uses a stable forwarded ref implementation`, () => {
    const source = readFileSync(path.join(__dirname, fileName), 'utf8')

    assert.match(source, /React\.forwardRef/)
    assert.doesNotMatch(source, /function [A-Z][A-Za-z0-9_]*\(\{[^)]*\bref\b/)
  })
}

test('checkbox.tsx avoids the React 19-incompatible radix checkbox primitive', () => {
  const source = readFileSync(path.join(__dirname, 'checkbox.tsx'), 'utf8')

  assert.doesNotMatch(source, /@radix-ui\/react-checkbox/)
})

test('select.tsx uses stable forwarded refs for all ref-bearing wrappers', () => {
  const source = readFileSync(path.join(__dirname, 'select.tsx'), 'utf8')

  const wrappers = [
    'SelectTrigger',
    'SelectContent',
    'SelectLabel',
    'SelectItem',
    'SelectSeparator',
    'SelectScrollUpButton',
    'SelectScrollDownButton',
  ]

  for (const wrapper of wrappers) {
    assert.match(source, new RegExp(`const ${wrapper} = React\\.forwardRef`))
  }

  assert.doesNotMatch(source, /function SelectTrigger\(\{[\s\S]*?\bref\b/)
  assert.doesNotMatch(source, /function SelectContent\(\{[\s\S]*?\bref\b/)
  assert.doesNotMatch(source, /function SelectLabel\(\{[\s\S]*?\bref\b/)
  assert.doesNotMatch(source, /function SelectItem\(\{[\s\S]*?\bref\b/)
  assert.doesNotMatch(source, /function SelectSeparator\(\{[\s\S]*?\bref\b/)
  assert.doesNotMatch(source, /function SelectScrollUpButton\(\{[\s\S]*?\bref\b/)
  assert.doesNotMatch(source, /function SelectScrollDownButton\(\{[\s\S]*?\bref\b/)
})
