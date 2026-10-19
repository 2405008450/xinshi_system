import { reactive } from 'vue'
import { topicApi } from '@/api/chatTopics'

const topics = reactive({ ready: false, can_manage: false, can_classify_others: false, items: [], error: '' })
let identity = '', refreshed = 0, pending
export function useChatTopics() {
  async function refresh(force = false) {
    const key = `${localStorage.getItem('user_id')}:${localStorage.getItem('token')}`
    if (key !== identity) {
      identity = key; refreshed = 0; pending = null
      Object.assign(topics, { ready: false, can_manage: false, can_classify_others: false, items: [], error: '' })
    }
    if (!force && Date.now() - refreshed < 30000) return topics
    if (pending) return pending
    pending = topicApi.tree().then(data => {
      if (key === identity) {
        const rows = new Map(topics.items.map(row => [row.id, row]))
        for (const row of data.items || []) if (!rows.has(row.id) || rows.get(row.id).revision <= row.revision) rows.set(row.id, row)
        Object.assign(topics, data, { items: data.ready ? [...rows.values()].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, 'zh-CN')) : [], error: '' }); refreshed = Date.now()
      }
      return topics
    }).catch(error => { if (key === identity) topics.error = error.message; throw error })
      .finally(() => { if (key === identity) pending = null })
    return pending
  }
  return { topics, refresh }
}
