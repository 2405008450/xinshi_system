import { find } from 'linkifyjs'

export function isWebUrl(value) {
  if (typeof value !== 'string' || !/^https?:\/\//i.test(value) || /[\s\\\u0000-\u001f\u007f]/.test(value)) return false
  try {
    return Boolean(new URL(value).hostname)
  } catch {
    return false
  }
}

export const noticeLinkOptions = {
  autolink: true,
  openOnClick: true,
  linkOnPaste: false,
  defaultProtocol: 'https',
  HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer nofollow' },
  isAllowedUri: value => isWebUrl(value) || (/^www\./i.test(value) && isWebUrl(`https://${value}`))
}

export function handleWebLinkClick(view, _pos, event) {
  const anchor = event.target?.closest?.('a[href]')
  if (event.button !== 0 || !anchor || !view.dom.contains(anchor) || !isWebUrl(anchor.href)) return false
  event.preventDefault()
  window.open(anchor.href, '_blank', 'noopener,noreferrer')
  return true
}

// 从可见文字重新识别网址，不保留剪贴板携带的隐藏链接或样式。
export function linkifyTextNode(node) {
  if (!node.text || node.marks?.some(mark => ['link', 'code'].includes(mark.type))) return [node]
  const matches = find(node.text, 'url', { defaultProtocol: 'https' }).filter(match => isWebUrl(match.href))
  const result = []
  let offset = 0
  for (const match of matches) {
    if (match.start > offset) result.push({ ...node, text: node.text.slice(offset, match.start) })
    result.push({ ...node, text: match.value, marks: [...(node.marks || []), {
      type: 'link', attrs: { href: match.href, target: '_blank', rel: 'noopener noreferrer nofollow' }
    }] })
    offset = match.end
  }
  if (offset < node.text.length) result.push({ ...node, text: node.text.slice(offset) })
  return result
}

export function linkifyDocument(document) {
  if (!document || document.type === 'codeBlock') return document
  return document.content ? {
    ...document,
    content: document.content.flatMap(node => node.type === 'text' ? linkifyTextNode(node) : [linkifyDocument(node)])
  } : document
}
