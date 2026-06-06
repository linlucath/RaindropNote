import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const homePageSource = readFileSync(join(__dirname, 'src/pages/HomePage/Home.tsx'), 'utf8')

test('home page splits heavy panel components behind lazy imports', () => {
  assert.match(homePageSource, /import\s*\{[^}]*lazy[^}]*Suspense[^}]*\}\s*from\s*['"]react['"]/)

  for (const componentName of ['NoteForm', 'MarkdownViewer', 'History']) {
    assert.doesNotMatch(
      homePageSource,
      new RegExp(`import\\s+${componentName}\\s+from\\s+['"][^'"]+${componentName}\\.tsx['"]`)
    )
    assert.match(
      homePageSource,
      new RegExp(
        `const\\s+${componentName}\\s*=\\s*lazy\\(\\(\\)\\s*=>\\s*import\\(['"][^'"]+${componentName}\\.tsx['"]\\)\\)`
      )
    )
  }

  assert.match(homePageSource, /<Suspense\s+fallback=\{null\}>\s*<NoteForm\s*\/>\s*<\/Suspense>/s)
  assert.match(
    homePageSource,
    /<Suspense\s+fallback=\{null\}>\s*<MarkdownViewer\s+status=\{status\}\s*\/>\s*<\/Suspense>/s
  )
  assert.match(homePageSource, /<Suspense\s+fallback=\{null\}>\s*<History\s*\/>\s*<\/Suspense>/s)
})
