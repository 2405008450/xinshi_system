import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export function useChatWorkspaceSplit(root, active, narrow, maximized) {
  const key = `xinshi.chatWorkspaceSplit.${localStorage.getItem('user_id') || 'anonymous'}`
  const preferred = ref(null), containerWidth = ref(0), dragging = ref(false)
  try {
    const value = JSON.parse(localStorage.getItem(key) || 'null')
    if (typeof value === 'number' && Number.isFinite(value) && value >= 220) preferred.value = value
  } catch { /* 无效配置使用默认分区。 */ }
  const defaultWidth = computed(() => maximized.value ? 300 : 280)
  const maximum = computed(() => Math.max(220, containerWidth.value - (maximized.value ? 56 : 0) - 320))
  const clamp = value => Math.round(Math.max(220, Math.min(maximum.value, value)))
  const width = computed(() => narrow.value ? 0 : clamp(preferred.value ?? defaultWidth.value))
  let observer, stopDrag
  function save() {
    try {
      if (preferred.value === null) localStorage.removeItem(key)
      else localStorage.setItem(key, JSON.stringify(preferred.value))
    } catch { /* 存储不可用时仍可调整本次布局。 */ }
  }
  function reset() { stopDrag?.(); preferred.value = null; save() }
  function keyboard(event) {
    if (narrow.value || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    preferred.value = event.key === 'Home' ? 220 : event.key === 'End' ? maximum.value : clamp(width.value + (event.key === 'ArrowLeft' ? -10 : 10))
    save()
  }
  function start(event) {
    if (event.button !== 0 || narrow.value) return
    event.preventDefault(); stopDrag?.()
    const begin = event.clientX, initial = width.value, pointer = event.pointerId
    const selection = document.body.style.userSelect, cursor = document.body.style.cursor
    document.body.style.userSelect = 'none'; document.body.style.cursor = 'col-resize'; dragging.value = true
    const move = e => { if (e.pointerId === pointer) preferred.value = clamp(initial + e.clientX - begin) }
    const finish = () => stopDrag?.()
    stopDrag = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish)
      window.removeEventListener('pointercancel', finish); window.removeEventListener('blur', finish)
      document.body.style.userSelect = selection; document.body.style.cursor = cursor
      dragging.value = false; stopDrag = undefined; save()
    }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', finish)
    window.addEventListener('pointercancel', finish); window.addEventListener('blur', finish)
  }
  watch(root, element => {
    observer?.disconnect()
    if (!element) return
    const measure = () => { if (element.clientWidth) containerWidth.value = element.clientWidth }
    measure(); observer = new ResizeObserver(measure); observer.observe(element)
  }, { flush: 'post' })
  watch(active, value => { if (!value) { stopDrag?.(); save() } })
  watch(narrow, () => stopDrag?.())
  onMounted(() => window.addEventListener('pagehide', save))
  onBeforeUnmount(() => { stopDrag?.(); observer?.disconnect(); save(); window.removeEventListener('pagehide', save) })
  return { width, maximum, dragging, start, keyboard, reset }
}
