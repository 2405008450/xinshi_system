import { isOptimisticMessage } from './chatOptimistic.js'

export const MAX_RETAINED_CHAT_MESSAGES = 200

/**
 * 在长会话中裁剪最早超出窗口的真实消息，防止 DOM 节点无限膨胀。
 * 乐观消息（发送中/发送失败）和受保护消息（如正在编辑的消息）始终保留。
 */
export function trimMessageWindow(messages, { maxReal = MAX_RETAINED_CHAT_MESSAGES, protectedIds = [] } = {}) {
  if (!Array.isArray(messages) || messages.length <= maxReal) {
    return { messages, trimmed: false }
  }
  const realMessages = messages.filter(item => !isOptimisticMessage(item))
  if (realMessages.length <= maxReal) {
    return { messages, trimmed: false }
  }
  const protectedSet = new Set(protectedIds.filter(Boolean).map(String))
  const keepRealIds = new Set(realMessages.slice(-maxReal).map(item => String(item.id)))
  const next = messages.filter(item => (
    isOptimisticMessage(item)
    || keepRealIds.has(String(item.id))
    || protectedSet.has(String(item.id))
  ))
  return {
    messages: next,
    trimmed: next.length < messages.length,
  }
}
