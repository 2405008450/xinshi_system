export const CHAT_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
export const CHAT_IMAGE_LIMIT = 9
export const CHAT_IMAGE_MAX_BYTES = 10 * 1024 * 1024

// 状态由调用者提供，兼容 Vue reactive，也便于验证异步上传竞态。
export function createChatImageQueue(items, { upload, createUrl, revokeUrl, warn }) {
  let sequence = 0
  const contains = item => items.some(value => value.key === item.key)
  async function retry(item) {
    if (!contains(item) || item.status === 'uploading') return
    item.status = 'uploading'
    item.error = ''
    try {
      const attachment = await upload(item.file)
      if (!contains(item)) return
      item.attachment = attachment
      item.status = 'ready'
    } catch (error) {
      if (!contains(item)) return
      item.status = 'failed'
      item.error = error?.response?.data?.detail || '图片上传失败，请重试或移除'
    }
  }
  function add(files) {
    for (const file of files) {
      if (!CHAT_IMAGE_TYPES.includes(file.type)) { warn('仅支持 JPEG、PNG、GIF、WebP 图片'); continue }
      if (!file.size || file.size > CHAT_IMAGE_MAX_BYTES) { warn('图片不能为空，且每张不能超过 10MB'); continue }
      if (items.length >= CHAT_IMAGE_LIMIT) { warn('每条留言最多添加 9 张图片'); break }
      items.push({ key: ++sequence, file, url: createUrl(file), status: 'pending', attachment: null, error: '' })
      // 从响应式数组重新读取，确保异步状态变更触发视图更新。
      void retry(items[items.length - 1])
    }
  }
  function remove(key) {
    const index = items.findIndex(item => item.key === key)
    if (index < 0) return
    revokeUrl(items[index].url)
    items.splice(index, 1)
  }
  function clear() {
    items.forEach(item => revokeUrl(item.url))
    items.splice(0)
  }
  return { add, retry, remove, clear }
}
