// 只按服务端提及关系高亮当前用户，不把普通的 @ 文本误认成提醒。
export function mentionParts(message, userId) {
  const recipient = (message.mentions || []).find(m => String(m.mentionedUserId) === String(userId))
  const name = recipient && (message.metadata?.mentionAll || message.metadata?.mention_all) && message.content?.includes('@所有人') ? '所有人' : recipient?.mentionedUserName
  const content = message.content || ''
  if (!name) return [{ text: content, highlight: false }]
  const token = `@${name}`
  return content.split(token).flatMap((text, index) => index ? [{ text: token, highlight: true }, { text, highlight: false }] : [{ text, highlight: false }])
}

export function mentionedDocument(message, userId) {
  const recipient = (message.mentions || []).find(m => String(m.mentionedUserId) === String(userId))
  const name = recipient && (message.metadata?.mentionAll || message.metadata?.mention_all) && message.content?.includes('@所有人') ? '所有人' : recipient?.mentionedUserName
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

// 自动项目消息的正文不包含 @ 文本时，仍展示服务端持久化的真实提及关系。
export function undisplayedMentions(message,userId){
  if(message.recalledAt||message.recalled_at)return []
  const mentions=message.mentions||[],content=message.content||''
  if(!mentions.length)return []
  const all=mentions.some(item=>item.isAll||item.is_all)||message.metadata?.mentionAll||message.metadata?.mention_all
  if(all)return content.includes('@所有人')||content.includes('@全体')?[]:[{id:'all',label:'@所有人',highlight:mentions.some(item=>String(item.mentionedUserId??item.mentioned_user_id)===String(userId))}]
  const unique=new Map()
  for(const item of mentions){
    const id=item.mentionedUserId??item.mentioned_user_id,name=item.mentionedUserName??item.mentioned_user_name
    if(id&&name&&!content.includes('@'+name))unique.set(String(id),{id:String(id),label:'@'+name,highlight:String(id)===String(userId)})
  }
  return [...unique.values()]
}
