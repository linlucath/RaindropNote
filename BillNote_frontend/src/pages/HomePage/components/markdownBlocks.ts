export const SOURCE_LINK_PATTERN = /^>\s*来源链接：[^\n]*\n*/m

export function stripSourceLink(markdown: string): string {
  return markdown.replace(SOURCE_LINK_PATTERN, '')
}

export function restoreSourceLink(originalMarkdown: string, visibleMarkdown: string): string {
  const match = originalMarkdown.match(SOURCE_LINK_PATTERN)
  if (!match || match.index !== 0) return visibleMarkdown
  return `${match[0]}${visibleMarkdown}`
}

export function splitMarkdownIntoBlocks(markdown: string): string[] {
  const normalized = markdown.replace(/\r\n/g, '\n')
  const lines = normalized.split('\n')
  const blocks: string[] = []
  let current: string[] = []
  let fenceMarker: string | null = null

  const flushCurrent = () => {
    const block = current.join('\n').trim()
    if (block) blocks.push(block)
    current = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    const fenceMatch = trimmed.match(/^(`{3,}|~{3,})/)

    if (fenceMatch) {
      const marker = fenceMatch[1]
      if (!fenceMarker) {
        fenceMarker = marker
      } else if (marker[0] === fenceMarker[0] && marker.length >= fenceMarker.length) {
        fenceMarker = null
      }
    }

    if (!fenceMarker && trimmed === '') {
      flushCurrent()
      continue
    }

    current.push(line)
  }

  flushCurrent()
  return blocks
}

export function joinMarkdownBlocks(blocks: string[]): string {
  return blocks
    .map(block => block.trim())
    .filter(Boolean)
    .join('\n\n')
}

export function replaceMarkdownBlock(blocks: string[], index: number, nextBlock: string): string[] {
  return blocks.map((block, blockIndex) => (blockIndex === index ? nextBlock : block))
}
