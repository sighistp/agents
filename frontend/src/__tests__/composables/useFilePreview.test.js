import { describe, it, expect } from 'vitest'
import { useFilePreview } from '../../composables/useFilePreview.js'

describe('useFilePreview', () => {
  it('openPreview 设置文件名和内容', () => {
    const { previewFile, previewContent, openPreview } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    expect(previewFile.value).toBe('main.py')
    expect(previewContent.value).toBe('print("hello")')
  })

  it('openPreview 生成语法高亮内容', () => {
    const { highlightedContent, openPreview } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    expect(highlightedContent.value).toContain('hljs')
  })

  it('closePreview 清空所有状态', () => {
    const { previewFile, previewContent, highlightedContent, openPreview, closePreview } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    closePreview()
    expect(previewFile.value).toBeNull()
    expect(previewContent.value).toBe('')
    expect(highlightedContent.value).toBe('')
  })

  it('copyContent 复制原始内容到剪贴板', async () => {
    const { openPreview, copyContent, previewContent } = useFilePreview()
    openPreview('main.py', 'print("hello")')
    // mock clipboard
    let copied = ''
    Object.assign(navigator, { clipboard: { writeText: async (t) => { copied = t } } })
    await copyContent()
    expect(copied).toBe('print("hello")')
  })

  it('未知扩展名用 highlightAuto', () => {
    const { highlightedContent, openPreview } = useFilePreview()
    openPreview('file.xyz', 'some content')
    expect(highlightedContent.value).toBeTruthy()
  })
})
