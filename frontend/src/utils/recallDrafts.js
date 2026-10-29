const memoryFiles = new Map()
const memoryDrafts = new Map()
const LIMIT = 30

export const recallDraftKey = (owner, kind, id) => `xinshi.chatRecallDraft.v1:${owner}:${kind}:${id}`

async function storedFiles(key, value, remove = false) {
  if (typeof indexedDB === 'undefined') return []
  return new Promise(resolve => {
    const open = indexedDB.open('xinshi-chat-recall-files', 1)
    open.onupgradeneeded = () => open.result.createObjectStore('files')
    open.onerror = () => resolve([])
    open.onblocked = () => resolve([])
    open.onsuccess = () => {
      const db = open.result, write = value !== undefined || remove
      try {
        const transaction = db.transaction('files', write ? 'readwrite' : 'readonly')
        const store = transaction.objectStore('files')
        const request = remove ? store.delete(key) : write ? store.put(value, key) : store.get(key)
        let result = []
        request.onsuccess = () => { result = request.result || [] }
        transaction.oncomplete = () => { db.close(); resolve(result) }
        transaction.onerror = transaction.onabort = () => { db.close(); resolve([]) }
      } catch { db.close(); resolve([]) }
    }
  })
}

export function captureRecallDraft(message, owner) {
  if (!message || String(message.senderUserId) !== String(owner) || message.recalledAt ||
      message.messageType && message.messageType !== 'user' ||
      !message.content?.trim() && !message.attachments?.length) return null
  const all = !!(message.metadata?.mentionAll || message.metadata?.mention_all || message.mentionAll)
  return JSON.parse(JSON.stringify({
    messageId: String(message.id), owner: String(owner), content: message.content || '',
    contentJson: message.contentJson || null,
    mentions: all ? [] : (message.mentions || []).map(person => ({ id: String(person.mentionedUserId), name: person.mentionedUserName })),
    mentionAll: all, replyTo: message.reply || null, attachmentCount: message.attachments?.length || 0,
  }))
}

export function combineRecallDraft(current, recovered) {
  if (!recovered.content && recovered.attachmentCount && !recovered.files?.length) throw new Error('原附件暂存不可用，请重新添加附件')
  const content = [current.content, recovered.content].filter(Boolean).join(current.content && recovered.content ? '\n' : '')
  if (content.length > 10000) throw new Error('恢复后内容超过10000字，请先处理输入框中的草稿')
  const mentionIds = [...new Set([...(current.mentionIds || []), ...recovered.mentions.map(person => person.id), ...(recovered.mentionAll ? ['__all__'] : [])])]
  if (mentionIds.filter(id => id !== '__all__').length > 20) throw new Error('恢复后提及人数超过20人，请先处理输入框中的草稿')
  const document = (text, json) => json?.content || text.split('\n').map(line => ({ type: 'paragraph', ...(line ? { content: [{ type: 'text', text: line }] } : {}) }))
  return { content, mentionIds,
    contentJson: { type: 'doc', content: [...(current.content ? document(current.content, current.contentJson) : []), ...document(recovered.content, recovered.contentJson)] },
    replyTo: current.replyTo || recovered.replyTo,
  }
}

export function createRecallDraftStore(storage) {
  function read(key) {
    if (memoryDrafts.has(key)) return memoryDrafts.get(key)
    try { const value = JSON.parse(storage.getItem(key) || 'null'); return value?.version === 1 && Array.isArray(value.items) ? value.items : [] } catch { return [] }
  }
  function write(key, items) { try { storage.setItem(key, JSON.stringify({ version: 1, items })); memoryDrafts.delete(key); return true } catch { memoryDrafts.set(key, items); return false } }
  return {
    read,
    async remember(key, message, owner, loadAttachment) {
      const snapshot = captureRecallDraft(message, owner)
      if (!snapshot) return null
      const items = [...read(key).filter(row => row.messageId !== snapshot.messageId), snapshot]
      const evicted = items.slice(0, -LIMIT)
      write(key, items.slice(-LIMIT))
      for (const row of evicted) { const fileKey = `${key}:${row.messageId}`; memoryFiles.delete(fileKey); void storedFiles(fileKey, undefined, true) }
      const files = []
      if (loadAttachment) {
        const results = await Promise.allSettled((message.attachments || []).map(async attachment => {
          const blob = await loadAttachment(attachment)
          return new File([blob], attachment.originalName || '附件', { type: attachment.contentType || blob.type })
        }))
        for (const result of results) if (result.status === 'fulfilled') files.push(result.value)
      }
      memoryFiles.set(`${key}:${snapshot.messageId}`, files)
      if (files.length) await storedFiles(`${key}:${snapshot.messageId}`, files)
      return snapshot
    },
    async restore(key, id, owner) {
      const snapshot = read(key).find(row => row.messageId === String(id) && row.owner === String(owner))
      if (!snapshot) return null
      const fileKey = `${key}:${id}`
      return { ...snapshot, files: memoryFiles.get(fileKey) || await storedFiles(fileKey) }
    },
    remove(key, id) {
      write(key, read(key).filter(row => row.messageId !== String(id)))
      const fileKey = `${key}:${id}`; memoryFiles.delete(fileKey); void storedFiles(fileKey, undefined, true)
    },
  }
}
