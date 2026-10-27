export const nativeMessageContextSelector = 'img, video, audio, a, input, textarea, [contenteditable="true"], .group-file, .message-attachment, .group-reply, button, [role="button"], [role="checkbox"]'

export function clampMessageMenu(point, size, viewport, gap = 8) {
  return {
    left: Math.max(gap, Math.min(point.x, viewport.width - size.width - gap)),
    top: Math.max(gap, Math.min(point.y, viewport.height - size.height - gap)),
  }
}

export function buildMessageMenu(message, { handlers = {}, currentUserId = '', canCollect = false, canProgress = false, annotationProgress = false, selecting = false, excerpt = '' } = {}) {
  if (!message || message.recalledAt) return []
  const normal = !message.messageType || message.messageType === 'user'
  const text = !!message.content?.trim()
  const items = []
  if (handlers.copy) items.push({ id: 'copy', label: excerpt ? '复制选中内容' : '复制', icon: 'copy' })
  if (normal && handlers.reply) items.push({ id: 'reply', label: '引用', icon: 'reply' })
  if (handlers.favorite) items.push({ id: 'favorite', label: message.isFavorited ? '取消收藏' : '收藏', icon: 'favorite' })
  if (normal && handlers.acknowledge && message.senderUserId !== currentUserId && (!handlers.canAcknowledge || handlers.canAcknowledge(message))) {
    items.push({ id: 'acknowledge', label: message.isAcknowledged ? '取消收到' : '收到', icon: 'acknowledge' })
  }
  if (normal && text && canCollect) items.push({ id: 'collect', label: '分类保存和通知', icon: 'collect', submenu: true, separator: true })
  if (normal && text && handlers.technical) items.push({id:'technical',label:'添加技术需求',icon:'technical',separator:true})
  if (normal && text && annotationProgress) items.push({id:'annotation-progress',label:'添加进度',icon:'progress',submenu:true,separator:true})
  else if (text && canProgress && handlers.progress) items.push({ id: 'progress', label: excerpt ? '添加选中内容为进度' : '添加为进度', icon: 'progress', separator: true })
  if (text && canProgress && handlers.select) items.push({ id: 'select', label: selecting ? '选择这条消息' : '多选', icon: 'select' })
  if (normal && message.senderUserId === currentUserId && message.canRecall && handlers.recall) items.push({ id: 'recall', label: '撤回', icon: 'recall', danger: true, separator: true })
  return items
}
