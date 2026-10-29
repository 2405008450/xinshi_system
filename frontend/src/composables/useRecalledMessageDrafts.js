import { computed, onBeforeUnmount, ref } from 'vue'
import { createRecallDraftStore, recallDraftKey } from '@/utils/recallDrafts'

export function useRecalledMessageDrafts(scope) {
  const owner = localStorage.getItem('user_id') || '', revision = ref(0)
  const store = createRecallDraftStore(localStorage)
  const restoring = new Set()
  const key = computed(() => recallDraftKey(owner, ...scope.value))
  const refresh = () => { revision.value++ }
  const announce = () => { refresh(); window.dispatchEvent(new Event('chat-recall-drafts-changed')) }
  window.addEventListener('storage', refresh)
  window.addEventListener('chat-recall-drafts-changed', refresh)
  onBeforeUnmount(() => { window.removeEventListener('storage', refresh); window.removeEventListener('chat-recall-drafts-changed', refresh) })
  return {
    canReedit(message) {
      void revision.value
      return localStorage.getItem('user_id') === owner && !!message.recalledAt && String(message.senderUserId) === owner && store.read(key.value).some(row => row.messageId === String(message.id) && row.owner === owner)
    },
    async remember(message, loadAttachment) { const saved = await store.remember(key.value, message, owner, loadAttachment); announce(); return saved },
    async restore(message) {
      if (!message.recalledAt || String(message.senderUserId) !== owner) return null
      const expected = key.value, requestKey = `${expected}:${message.id}`
      if (restoring.has(requestKey)) return null
      restoring.add(requestKey)
      try {
        const result = await store.restore(expected, message.id, owner)
        return expected === key.value && localStorage.getItem('user_id') === owner ? result : null
      } finally { restoring.delete(requestKey) }
    },
    forget(message) { store.remove(key.value, message.id); announce() },
  }
}
