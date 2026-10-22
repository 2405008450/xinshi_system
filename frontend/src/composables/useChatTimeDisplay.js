import { computed, ref, watch } from 'vue'
import { chatDateLabel, chatMessageTime } from '@/utils/chatLayout'

const modes = ['full', 'hidden', 'no-year', 'time']
const preferences = new Map()
const prefix = 'xinshi.chatTimeDisplay.'
const normalize = value => modes.includes(value) ? value : 'full'

if (typeof window !== 'undefined') window.addEventListener('storage', event => {
  if (event.key?.startsWith(prefix) && preferences.has(event.key)) preferences.get(event.key).value = normalize(event.newValue)
})

export function useChatTimeDisplay() {
  let userId = 'anonymous'
  try { userId = localStorage.getItem('user_id') || userId } catch { /* 使用本次会话偏好。 */ }
  const key = prefix + userId
  if (!preferences.has(key)) {
    let saved = 'full'
    try { saved = normalize(localStorage.getItem(key)) } catch { /* 保持默认显示。 */ }
    const mode = ref(saved)
    watch(mode, value => {
      try { localStorage.setItem(key, normalize(value)) } catch { /* 存储不可用仍即时生效。 */ }
    }, { flush: 'sync' })
    preferences.set(key, mode)
  }
  const mode = preferences.get(key)
  return {
    mode,
    showMessageTime: computed(() => mode.value !== 'hidden'),
    showMessageDates: computed(() => ['full', 'no-year'].includes(mode.value)),
    formatMessageTime: value => chatMessageTime(value, new Date(), mode.value),
    formatMessageDay: value => {
      const label = chatDateLabel(value, new Date(), true)
      return mode.value === 'no-year' ? label.replace(/\d{4}年/g, '') : label
    },
  }
}
