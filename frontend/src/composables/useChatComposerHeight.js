import { computed, onBeforeUnmount, ref } from 'vue'

/** 按用户保存输入区高度；预留消息流和固定发送栏的可见空间。 */
export function useChatComposerHeight() {
  let key = 'xinshi.chatComposerHeight.anonymous'
  let saved = 80
  try { key = `xinshi.chatComposerHeight.${localStorage.getItem('user_id') || 'anonymous'}`; saved = Number(localStorage.getItem(key)) || 80 } catch { /* 存储不可用时使用默认高度。 */ }
  const height = ref(Math.max(64, Math.min(240, saved)))
  const composerStyle = computed(() => ({ '--chat-composer-height': `${height.value}px` }))
  const inputStyle = computed(() => ({ height: `min(${height.value}px, 25dvh)`, minHeight: '0', maxHeight: 'min(240px, 25dvh)' }))
  let startY = 0, startHeight = 0, changed = false
  function move(event) { height.value = Math.max(64, Math.min(240, window.innerHeight * .25, startHeight + startY - event.clientY)); changed = true }
  function stop() {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    window.removeEventListener('pointercancel', stop)
    if (changed) {
      try { localStorage.setItem(key, String(height.value)) } catch { /* 本次高度仍生效。 */ }
      changed = false
    }
  }
  function start(event) {
    if (event.button !== 0) return
    event.preventDefault(); startY = event.clientY; startHeight = height.value
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
  }
  function resizeByKeyboard(event) {
    if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return
    event.preventDefault(); height.value = Math.max(64, Math.min(240, height.value + (event.key === 'ArrowUp' ? 16 : -16))); changed = true; stop()
  }
  onBeforeUnmount(stop)
  return { composerStyle, inputStyle, start, resizeByKeyboard }
}
