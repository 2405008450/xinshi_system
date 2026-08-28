import { onBeforeUnmount, onMounted, ref } from 'vue'
import { MINUTE_MS } from '@/utils/deadlineDisplay'

const subscribers = new Set()
let sharedTimer = null

function emitTick() {
  const now = Date.now()
  subscribers.forEach((tickRef) => {
    tickRef.value = now
  })
}

export function useDeadlineNow() {
  const nowTick = ref(Date.now())

  onMounted(() => {
    nowTick.value = Date.now()
    subscribers.add(nowTick)
    if (!sharedTimer) {
      sharedTimer = window.setInterval(emitTick, MINUTE_MS)
    }
  })

  onBeforeUnmount(() => {
    subscribers.delete(nowTick)
    if (!subscribers.size && sharedTimer) {
      window.clearInterval(sharedTimer)
      sharedTimer = null
    }
  })

  return nowTick
}
