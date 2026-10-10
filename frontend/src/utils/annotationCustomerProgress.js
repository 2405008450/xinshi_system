import { businessDateTimeInputValue } from './dateTime.js'

export const appendProgressDraft = (existing, incoming) => {
  const content = [String(existing || '').trim(), String(incoming || '').trim()].filter(Boolean).join('\n\n')
  if (content.length > 10000) throw new Error('合并后的具体进度超过 10000 字，请先整理内容')
  return content
}

export const progressChatDraft = (messages) => {
  const rows = (Array.isArray(messages) ? messages : [messages])
    .filter((message) => String(message?.content || '').trim())
    .map((message, index) => ({ message, index, timestamp: message.createdAt ? Date.parse(businessDateTimeInputValue(message.createdAt).replace(' ', 'T') + '+08:00') : NaN }))
    .sort((left, right) => (Number.isFinite(left.timestamp) ? left.timestamp : Infinity) - (Number.isFinite(right.timestamp) ? right.timestamp : Infinity) || left.index - right.index)
  if (!rows.length) throw new Error('请先选择包含文字内容的沟通消息')
  const changeNote = rows.map(({ message }) => `【${message.senderName || '未知用户'}】\n${String(message.content).trim()}`).join('\n\n')
  appendProgressDraft('', changeNote)
  const latest = rows.filter((row) => Number.isFinite(row.timestamp)).at(-1)
  return {
    changeNote,
    effectiveOn: businessDateTimeInputValue(latest ? new Date(latest.timestamp) : new Date()),
    source: { messageCount: rows.length, senderSummary: [...new Set(rows.map(({ message }) => message.senderName || '未知用户'))].join('、') },
  }
}
