export function clearAutomaticQuoteMention(content, selectedUsers, automatic) {
  let text = content || ''
  if (automatic?.token && text.startsWith(automatic.token)) text = text.slice(automatic.token.length)
  const people = (selectedUsers || []).filter(person => !automatic || person.id !== automatic.id || text.includes(automatic.token))
  return { content: text, selectedUsers: people, automatic: null }
}

export function quoteSpeakerMention({content, selectedUsers = [], automatic, message, currentUserId, users = []}) {
  const result = clearAutomaticQuoteMention(content, selectedUsers, automatic)
  const speakerId = message?.senderUserId
  const person = users.find(user => String(user.id) === String(speakerId) && !user.outside && user.isActive !== false)
  if (!speakerId || String(speakerId) === String(currentUserId) || !person?.name) return result
  const token = `@${person.name} `
  const alreadySelected = result.selectedUsers.some(user => user.id === person.id)
  if (!alreadySelected && result.selectedUsers.filter(user => !user.all && user.id !== '__all__').length >= 20) return {...result, warning: '每条消息最多提及20人，已保留引用，请调整提及人员'}
  if (!result.content.includes(token)) {
    if (result.content.length + token.length > 10000) return {...result, warning: '消息内容过长，未能自动添加提及，请缩短内容'}
    result.content = token + result.content
    result.automatic = {id:person.id,token}
  }
  if (!alreadySelected) result.selectedUsers.push({...person})
  return result
}
