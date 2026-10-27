import { onBeforeUnmount, ref } from 'vue'

export const MOBILE_VIEWPORT_QUERY = '(max-width: 768px)'

export function useMobileViewport(query = MOBILE_VIEWPORT_QUERY) {
  const supported = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  const media = supported ? window.matchMedia(query) : null
  const isMobile = ref(Boolean(media?.matches))
  const sync = (event) => { isMobile.value = event.matches }

  if (media) {
    media.addEventListener('change', sync)
    onBeforeUnmount(() => media.removeEventListener('change', sync))
  }

  return { isMobile }
}
