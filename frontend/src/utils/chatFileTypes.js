export const chatMediaExtensions = ['.mp4', '.mp3', '.wav', '.m4a', '.webm']
export const chatFileAccept = '.jpg,.jpeg,.png,.gif,.webp,.pdf,.txt,.csv,.zip,.doc,.xls,.ppt,.docx,.xlsx,.pptx,' + chatMediaExtensions.join(',')
export const chatFileHint = '每条最多9个附件；图片10MB，音视频100MB，其他文件20MB；支持MP4、MP3、WAV、M4A、WebM'
export function chatFileCategory(name) {
  const ext = '.' + (name || '').split('.').pop().toLowerCase()
  return chatMediaExtensions.includes(ext) ? 'media' : ['.jpg','.jpeg','.png','.gif','.webp'].includes(ext) ? 'image' : 'file'
}
export const chatFileMaxBytes = name => ({image:10, media:100, file:20}[chatFileCategory(name)] * 1024 * 1024)

export const chatFileSupported = name => chatFileAccept.split(',').includes('.' + (name || '').split('.').pop().toLowerCase())

// 部分浏览器仅在 items 提供文件；优先 files，避免同一附件被读取两次。
export function chatClipboardFiles(clipboard) {
  if (!clipboard) return []
  const files = Array.from(clipboard.files || [])
  if (files.length) return files
  return Array.from(clipboard.items || [])
    .filter(item => item.kind === 'file')
    .map(item => item.getAsFile())
    .filter(Boolean)
}
