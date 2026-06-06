import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

test('markdown viewer uses PrismLight with an explicit language allowlist', () => {
  const source = readFileSync(
    join(__dirname, 'src/pages/HomePage/components/MarkdownViewer.tsx'),
    'utf8'
  )

  assert.doesNotMatch(source, /Prism as SyntaxHighlighter/)
  assert.match(source, /PrismLight as SyntaxHighlighter/)

  for (const language of ['javascript', 'typescript', 'python', 'bash', 'json', 'tsx', 'css']) {
    assert.match(source, new RegExp(`registerLanguage\\(['"]${language}['"]`))
  }
})
