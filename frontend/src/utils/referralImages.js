export const REFERRAL_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp']
export const REFERRAL_IMAGE_MAX_BYTES = 5 * 1024 * 1024
const categories = new Set(['pull', 'moments', 'groups', 'qr'])

// 优先读取 items，避免同一剪贴板图片在 items 与 files 中被重复加入。
export function referralClipboardImages(data) {
  const items = Array.from(data?.items || [])
    .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
    .map(item => item.getAsFile()).filter(Boolean)
  return items.length ? items : Array.from(data?.files || []).filter(file => file.type.startsWith('image/'))
}

export function pasteReferralImages(event, receive, { disabled = false, preserveText = false } = {}) {
  const images = referralClipboardImages(event.clipboardData)
  if (!images.length) return false
  // 说明框中的混合图文保留原生文字粘贴及撤销行为。
  if (!preserveText || !event.clipboardData.getData('text/plain')) event.preventDefault()
  if (!disabled) receive(images)
  return true
}

export function referralImageError(file) {
  if (!REFERRAL_IMAGE_TYPES.includes(file.type)) return '仅支持 PNG、JPEG、WebP 图片'
  if (!file.size) return '图片不能为空'
  if (file.size > REFERRAL_IMAGE_MAX_BYTES) return '每张图片不能超过5MB'
  return ''
}

export function releaseReferralDrafts(items, urls = URL) {
  for (const item of items) urls.revokeObjectURL(item.previewUrl)
}

export function queueReferralImages(current, incoming, category, { createId, urls = URL }) {
  if (!categories.has(category)) throw new Error('未知图片类别')
  const errors = [], valid = []
  for (const file of incoming) {
    const error = referralImageError(file)
    if (error) errors.push(`${file.name || '剪贴板图片'}：${error}`)
    else valid.push(file)
  }
  if (!valid.length) return { items: current, errors }
  // 多张图片进入单码区域时保留最后一张，不产生多余的预览资源。
  const selected = category === 'qr' ? valid.slice(-1) : valid
  const additions = selected.map(file => ({ id: createId(), file, category, error: '', previewUrl: urls.createObjectURL(file) }))
  const replaced = category === 'qr' ? current.filter(item => item.category === 'qr') : []
  releaseReferralDrafts(replaced, urls)
  return { items: [...current.filter(item => !replaced.includes(item)), ...additions], errors }
}

export function removeReferralDraft(items, id, urls = URL) {
  releaseReferralDrafts(items.filter(item => item.id === id), urls)
  return items.filter(item => item.id !== id)
}
