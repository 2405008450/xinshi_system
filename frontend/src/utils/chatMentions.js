// 只按服务端提及关系高亮当前用户，不把普通的 @ 文本误认成提醒。
export function mentionParts(message, userId) {
  const name = (message.mentions || []).find(m => String(m.mentionedUserId) === String(userId))?.mentionedUserName
  const content = message.content || ''
  if (!name) return [{ text: content, highlight: false }]
  const token = `@${name}`
  return content.split(token).flatMap((text, index) => index ? [{ text: token, highlight: true }, { text, highlight: false }] : [{ text, highlight: false }])
}

export function mentionedDocument(message, userId) {
  const name = (message.mentions || []).find(m => String(m.mentionedUserId) === String(userId))?.mentionedUserName
  if (!name) return message.contentJson
  const document = message.contentJson || { type: 'doc', content: [{ type: 'paragraph', content: message.content ? [{ type: 'text', text: message.content }] : [] }] }
  const token = `@${name}`
  const decorate = node => {
    if (node.type === 'text' && node.text?.includes(token)) {
      return node.text.split(token).flatMap((text, index) => [
        ...(index ? [{ ...node, text: token, marks: [...(node.marks || []).filter(m => m.type !== 'highlight'), { type: 'highlight' }] }] : []),
        ...(text ? [{ ...node, text }] : []),
      ])
    }
    return [{ ...node, ...(node.content ? { content: node.content.flatMap(decorate) } : {}) }]
  }
  return decorate(document)[0]
}
