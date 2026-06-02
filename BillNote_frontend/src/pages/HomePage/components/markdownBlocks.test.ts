import assert from 'node:assert/strict'
import test from 'node:test'

import {
  joinMarkdownBlocks,
  replaceMarkdownBlock,
  restoreSourceLink,
  splitMarkdownIntoBlocks,
  stripSourceLink,
} from './markdownBlocks.ts'

test('splitMarkdownIntoBlocks keeps fenced code with blank lines as one block', () => {
  const blocks = splitMarkdownIntoBlocks('# 标题\n\n正文\n\n```ts\nconst a = 1\n\nconst b = 2\n```\n\n结尾')

  assert.deepEqual(blocks, ['# 标题', '正文', '```ts\nconst a = 1\n\nconst b = 2\n```', '结尾'])
})

test('replaceMarkdownBlock updates one block and joinMarkdownBlocks rebuilds the document', () => {
  const blocks = ['# 标题', '旧段落', '结尾']
  const nextBlocks = replaceMarkdownBlock(blocks, 1, '新段落')

  assert.equal(joinMarkdownBlocks(nextBlocks), '# 标题\n\n新段落\n\n结尾')
})

test('stripSourceLink and restoreSourceLink hide the source line while preserving saved content', () => {
  const original = '> 来源链接：https://example.com\n# 标题\n\n正文'
  const visible = stripSourceLink(original)

  assert.equal(visible, '# 标题\n\n正文')
  assert.equal(restoreSourceLink(original, '# 标题\n\n新正文'), '> 来源链接：https://example.com\n# 标题\n\n新正文')
})
