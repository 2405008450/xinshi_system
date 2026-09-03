const legacyCopy = (value, documentRef) => {
  if (!documentRef?.body || typeof documentRef.execCommand !== 'function') return false

  const textarea = documentRef.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  documentRef.body.appendChild(textarea)

  try {
    textarea.focus()
    textarea.select()
    textarea.setSelectionRange(0, value.length)
    return documentRef.execCommand('copy')
  } catch {
    return false
  } finally {
    textarea.remove()
  }
}

/**
 * 复制文本到剪贴板。
 * 局域网 HTTP 页面可能无法使用 Clipboard API，此时自动降级为传统复制方式。
 */
export const copyTextToClipboard = async (
  text,
  {
    clipboard = globalThis.navigator?.clipboard,
    documentRef = globalThis.document,
  } = {},
) => {
  const value = String(text ?? '')
  if (!value) return false

  if (typeof clipboard?.writeText === 'function') {
    try {
      await clipboard.writeText(value)
      return true
    } catch {
      // 非安全上下文或剪贴板权限被拒绝时，继续尝试兼容方案。
    }
  }

  return legacyCopy(value, documentRef)
}
