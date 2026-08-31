import { computed, ref } from 'vue'

export const UI_ZOOM_LEVELS = [0.8, 0.9, 1, 1.1, 1.25]
export const UI_ZOOM_DEFAULT = 1
export const UI_ZOOM_STORAGE_KEY = 'ui-zoom'

function getUserKey() {
  try {
    return localStorage.getItem('user_id') || localStorage.getItem('user_name') || ''
  } catch {
    return ''
  }
}

function userStorageKey(userKey = getUserKey()) {
  return userKey ? `${UI_ZOOM_STORAGE_KEY}:${userKey}` : UI_ZOOM_STORAGE_KEY
}

export function normalizeUiZoom(value) {
  const level = Number(value)
  return UI_ZOOM_LEVELS.includes(level) ? level : UI_ZOOM_DEFAULT
}

function clearZoomStyles(el) {
  if (!el) return
  el.style.removeProperty('zoom')
  el.style.removeProperty('transform')
  el.style.removeProperty('transform-origin')
  el.style.removeProperty('width')
  el.style.removeProperty('height')
}

export function applyUiZoom(zoom) {
  const level = normalizeUiZoom(zoom)
  const root = document.documentElement
  const body = document.body
  root.style.setProperty('--ui-zoom', String(level))
  // 旧实现把 zoom 写在 html 上，视口 overflow:hidden 会裁掉补偿宽度。
  clearZoomStyles(root)
  // 旧版本曾缩放 body；必须显式清理，避免它和新的应用层缩放叠加。
  clearZoomStyles(body)

  // 只缩放应用根节点。Element Plus 的浮层 Teleport 到 body 后仍处于正常
  // 视口坐标系，Popper 可直接使用触发元素的视觉坐标，避免缩放后错位。
  const target = document.getElementById('app')
  if (!target) return level
  if (level === 1) {
    clearZoomStyles(target)
    return level
  }

  target.style.zoom = String(level)
  target.style.width = `${100 / level}vw`
  target.style.height = `${100 / level}vh`
  return level
}

export function readStoredUiZoom() {
  try {
    const userKey = getUserKey()
    if (userKey) {
      const userValue = localStorage.getItem(userStorageKey(userKey))
      if (userValue != null) return normalizeUiZoom(userValue)
    }
    const fallback = localStorage.getItem(UI_ZOOM_STORAGE_KEY)
    if (fallback != null) return normalizeUiZoom(fallback)
  } catch {
    // ignore storage access errors
  }
  return UI_ZOOM_DEFAULT
}

export function persistUiZoom(zoom) {
  const level = normalizeUiZoom(zoom)
  try {
    localStorage.setItem(userStorageKey(), String(level))
    localStorage.setItem(UI_ZOOM_STORAGE_KEY, String(level))
  } catch {
    // ignore storage access errors
  }
  return level
}

const zoom = ref(readStoredUiZoom())
const panelVisible = ref(false)

applyUiZoom(zoom.value)

export function useUiZoom() {
  const zoomPercent = computed(() => Math.round(zoom.value * 100))

  function setZoom(value) {
    const level = persistUiZoom(value)
    zoom.value = level
    applyUiZoom(level)
  }

  function resetZoom() {
    setZoom(UI_ZOOM_DEFAULT)
  }

  const currentIndex = computed(() => UI_ZOOM_LEVELS.indexOf(zoom.value))
  const canStepDown = computed(() => currentIndex.value > 0)
  const canStepUp = computed(() => {
    const index = currentIndex.value
    return index >= 0 && index < UI_ZOOM_LEVELS.length - 1
  })

  function stepDown() {
    const index = currentIndex.value
    if (index > 0) {
      setZoom(UI_ZOOM_LEVELS[index - 1])
    }
  }

  function stepUp() {
    const index = currentIndex.value
    if (index >= 0 && index < UI_ZOOM_LEVELS.length - 1) {
      setZoom(UI_ZOOM_LEVELS[index + 1])
    }
  }

  function openPanel() {
    panelVisible.value = true
  }

  function syncFromStorage() {
    const level = readStoredUiZoom()
    zoom.value = level
    applyUiZoom(level)
  }

  return {
    zoom,
    zoomPercent,
    panelVisible,
    levels: UI_ZOOM_LEVELS,
    setZoom,
    resetZoom,
    canStepDown,
    canStepUp,
    stepDown,
    stepUp,
    openPanel,
    syncFromStorage,
  }
}
