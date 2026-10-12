import { reactive } from 'vue'
import { issueApi } from '@/api/resourceIssues'

const access = reactive({ ready: false, can_enter: false, can_collect: false, can_manage: false, can_resource: false, user_id: '', user_name: '' })
const collector = reactive({ visible: false, messageId: '', category: '' })
let identity = '', refreshedAt = 0, pending

export async function refreshIssueAccess(force = false) {
  const key = `${localStorage.getItem('user_id')}:${localStorage.getItem('token')}`
  if (key !== identity) {
    identity = key; refreshedAt = 0; pending = null
    Object.assign(access, { ready: false, can_enter: false, can_collect: false, can_manage: false, can_resource: false, user_id: '', user_name: '' })
    collector.visible = false
  }
  if (!force && refreshedAt && Date.now() - refreshedAt < 30000) return access
  if (pending) return pending
  pending = issueApi.access().then(value => {
    if (identity === key) { Object.assign(access, value); refreshedAt = Date.now() }
    return access
  }).finally(() => { if (identity === key) pending = null })
  return pending
}

export function useResourceIssues() {
  function collect(messageId, category) { Object.assign(collector, { visible: true, messageId, category }) }
  return { access, collector, collect, refreshIssueAccess }
}
