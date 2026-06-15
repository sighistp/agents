import { ref } from 'vue'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'
import json from 'highlight.js/lib/languages/json'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('json', json)

const LANG_MAP = { '.py': 'python', '.js': 'javascript', '.css': 'css', '.html': 'html', '.json': 'json' }

export function useFilePreview() {
  const previewFile = ref(null)
  const previewContent = ref('')
  const highlightedContent = ref('')

  function openPreview(path, content) {
    previewFile.value = path
    previewContent.value = content
    const ext = '.' + path.split('.').pop()
    const lang = LANG_MAP[ext]
    const raw = lang ? hljs.highlight(content, { language: lang }).value : hljs.highlightAuto(content).value
    highlightedContent.value = DOMPurify.sanitize(raw)
  }

  function closePreview() {
    previewFile.value = null
    previewContent.value = ''
    highlightedContent.value = ''
  }

  async function copyContent() {
    await navigator.clipboard.writeText(previewContent.value)
  }

  return { previewFile, previewContent, highlightedContent, openPreview, closePreview, copyContent }
}
