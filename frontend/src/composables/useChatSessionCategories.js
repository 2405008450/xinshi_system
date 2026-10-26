import { reactive } from 'vue'
import { chatRequest } from '@/api/projectChat'

export const sessionCategories = reactive({ ready: false, hierarchyReady: false, loaded: false, canManage: false, items: [] })
export function applySessionCategories(data) {
  if (data?.ready) {
    // 分类只停用不删除，保留较新修订，避免较早的轮询响应覆盖刚保存的结果。
    const rows = new Map(sessionCategories.items.map(row => [row.id, row]))
    for (const row of data.items || []) if (!rows.has(row.id) || rows.get(row.id).revision <= row.revision) rows.set(row.id, row)
    Object.assign(sessionCategories, data, { items: [...rows.values()], loaded: true })
  } else Object.assign(sessionCategories, { ready: false, hierarchyReady: false, loaded: !!data, canManage: false, items: [] }, data || {})
}
export const categoryKey = id => `category:${id}`
export function useChatSessionCategories() {
  const refresh = async () => {
    const identity = `${localStorage.getItem('user_id')}:${localStorage.getItem('token')}`
    const data = await chatRequest('session-categories')
    if (identity === `${localStorage.getItem('user_id')}:${localStorage.getItem('token')}`) applySessionCategories(data)
  }
  function accept(row) { const index = sessionCategories.items.findIndex(item => item.id === row.id); if (index < 0) sessionCategories.items.push(row); else sessionCategories.items[index] = row }
  const create = async (name, parentKey = null, conversation = false, directory = false) => { const row = await chatRequest('session-categories', { method: 'post', data: { name, parentKey, conversation, directory } }); accept(row); await refresh().catch(() => {}); return row }
  const update = async (row, data) => { const saved = await chatRequest(`session-categories/${row.id}`, { method: 'put', data: { ...data, revision: row.revision } }); accept(saved); await refresh().catch(() => {}); return saved }
  return { categories: sessionCategories, refresh, create, update }
}
