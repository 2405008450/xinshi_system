const DEFAULT_SCROLL_OPTIONS = {
  behavior: 'smooth',
  block: 'center',
  inline: 'nearest',
}

export const FORM_CONTROL_SELECTOR = [
  '.el-select__wrapper:not(.is-disabled)',
  'input:not([disabled])',
  'textarea:not([disabled]):not([readonly])',
  'select:not([disabled])',
  'button:not([disabled])',
  '[role="slider"]',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const waitForLayout = () => new Promise((resolve) => {
  if (typeof requestAnimationFrame !== 'function') {
    resolve()
    return
  }
  requestAnimationFrame(() => requestAnimationFrame(resolve))
})

const ancestors = (element, selector) => {
  const matches = []
  let current = element?.parentElement
  while (current) {
    if (current.matches?.(selector)) matches.push(current)
    if (current.classList?.contains('el-dialog')) break
    current = current.parentElement
  }
  return matches.reverse()
}

/**
 * 展开字段所在的标签页与折叠面板，保证隐藏字段在定位前进入可见状态。
 */
export async function revealFormTarget(target) {
  if (!target) return false
  let changed = false

  for (const pane of ancestors(target, '.el-tab-pane')) {
    if (pane.getAttribute?.('aria-hidden') !== 'true' && pane.style?.display !== 'none') continue
    const paneId = pane.id
    const tab = paneId && typeof document !== 'undefined'
      ? document.querySelector?.(`[role="tab"][aria-controls="${paneId}"]`)
      : null
    if (tab?.getAttribute?.('aria-selected') !== 'true') {
      tab.click?.()
      changed = true
      await waitForLayout()
    }
  }

  for (const item of ancestors(target, '.el-collapse-item')) {
    if (item.classList?.contains('is-active')) continue
    item.querySelector?.('.el-collapse-item__header')?.click?.()
    changed = true
    await waitForLayout()
  }

  if (changed) await waitForLayout()
  return changed
}

export function findScrollableFormContainer(target, preferredRoot) {
  let current = target?.parentElement
  while (current) {
    const style = typeof window !== 'undefined' && window.getComputedStyle
      ? window.getComputedStyle(current)
      : null
    if (style && /(auto|scroll)/.test(style.overflowY) && current.scrollHeight > current.clientHeight) {
      return current
    }
    if (current.classList?.contains('el-dialog')) break
    current = current.parentElement
  }

  if (preferredRoot) {
    const style = typeof window !== 'undefined' && window.getComputedStyle
      ? window.getComputedStyle(preferredRoot)
      : null
    if (style && /(auto|scroll)/.test(style.overflowY) && preferredRoot.scrollHeight > preferredRoot.clientHeight) {
      return preferredRoot
    }
  }

  return null
}

export function focusFormTarget(target) {
  const control = target?.querySelector?.(FORM_CONTROL_SELECTOR)
  if (!control || control.getAttribute?.('aria-disabled') === 'true') return false
  try {
    control.focus?.({ preventScroll: true })
  } catch {
    control.focus?.()
  }
  return true
}

export function scrollFormTarget(target, preferredRoot, options = DEFAULT_SCROLL_OPTIONS) {
  if (!target) return false
  const container = findScrollableFormContainer(target, preferredRoot)
  if (!container?.getBoundingClientRect || !target.getBoundingClientRect || !container.scrollTo) {
    target.scrollIntoView?.(options)
    return true
  }

  const containerRect = container.getBoundingClientRect()
  const targetRect = target.getBoundingClientRect()
  const targetTop = container.scrollTop + targetRect.top - containerRect.top
    - Math.max(0, (container.clientHeight - targetRect.height) / 2)
  container.scrollTo({ top: Math.max(0, targetTop), behavior: options.behavior || 'smooth' })
  return true
}

export { DEFAULT_SCROLL_OPTIONS, waitForLayout }
