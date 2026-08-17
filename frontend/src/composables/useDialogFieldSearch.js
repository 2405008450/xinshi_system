import { nextTick, onBeforeUnmount, ref } from 'vue'

const normalize = (value) => String(value || '').toLocaleLowerCase().replace(/\s+/g, '')

const directText = (element) => {
  if (!element) return ''
  return Array.from(element.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent)
    .join('')
    .trim()
}

const sectionName = (formItem) => {
  const section = formItem.closest('.form-section')
  if (!section) return '项目表单'
  const heading = section.querySelector('h3')
  return directText(heading) || heading?.textContent?.trim() || '项目表单'
}

const groupName = (formItem) => {
  const group = formItem.closest('.repeat-card, .price-card, .interpreter-requirement-group')
  if (!group) return ''
  const heading = group.querySelector('.repeat-title, .requirement-group-title')
  return directText(heading) || heading?.textContent?.trim() || ''
}

const findScrollableContainer = (start) => {
  let current = start
  while (current?.parentElement) {
    const style = window.getComputedStyle(current)
    if (/(auto|scroll)/.test(style.overflowY) && current.scrollHeight > current.clientHeight) return current
    if (current.classList.contains('el-dialog')) break
    current = current.parentElement
  }
  return start
}

export const useDialogFieldSearch = (editorBodyRef) => {
  const fieldSearchRef = ref(null)
  const fieldSearchKeyword = ref('')
  let highlightedElement = null
  let highlightTimer = null
  let suggestionTargets = new Map()

  const clearHighlight = () => {
    if (highlightTimer) window.clearTimeout(highlightTimer)
    highlightTimer = null
    highlightedElement?.classList.remove('is-dialog-field-search-highlight')
    highlightedElement = null
  }

  const clearFieldSearch = () => {
    fieldSearchKeyword.value = ''
    clearHighlight()
  }

  const collectFields = () => {
    const root = editorBodyRef.value
    if (!root) return []
    const occurrences = new Map()
    suggestionTargets = new Map()
    return Array.from(root.querySelectorAll('.el-form-item')).flatMap((element, index) => {
      const labelElement = element.querySelector(':scope > .el-form-item__label, :scope > label.el-form-item__label')
      const label = labelElement?.textContent?.trim().replace(/[：:]$/, '')
      if (!label) return []
      const section = sectionName(element)
      const group = groupName(element)
      const occurrenceKey = `${section}|${group}|${label}`
      const occurrence = (occurrences.get(occurrenceKey) || 0) + 1
      occurrences.set(occurrenceKey, occurrence)
      const key = `dialog-field-${index}`
      suggestionTargets.set(key, element)
      return [{
        key,
        label: occurrence > 1 ? `${label} ${occurrence}` : label,
        searchLabel: label,
        location: [section, group].filter(Boolean).join(' · '),
      }]
    })
  }

  const scoreField = (item, keyword) => {
    const label = normalize(item.searchLabel)
    const location = normalize(item.location)
    if (label === keyword) return 0
    if (label.startsWith(keyword)) return 1
    if (label.includes(keyword)) return 2
    if (location.includes(keyword)) return 3
    return Number.POSITIVE_INFINITY
  }

  const fetchFieldSuggestions = (queryString, callback) => {
    const keyword = normalize(queryString)
    if (!keyword) return callback([])
    const matches = collectFields()
      .map((item, index) => ({ item, index, score: scoreField(item, keyword) }))
      .filter(({ score }) => Number.isFinite(score))
      .sort((left, right) => left.score - right.score || left.index - right.index)
      .map(({ item }) => item)
    callback(matches)
  }

  const focusField = (target) => {
    const focusTarget = target.querySelector([
      'input:not([disabled]):not([readonly])',
      'textarea:not([disabled]):not([readonly])',
      'button:not([disabled])',
      '[role="slider"]',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', '))
    if (!focusTarget?.focus) return
    try { focusTarget.focus({ preventScroll: true }) } catch { focusTarget.focus() }
  }

  const locateDialogField = async (item) => {
    let target = suggestionTargets.get(item?.key)
    if (!target?.isConnected) {
      collectFields()
      target = suggestionTargets.get(item?.key)
    }
    if (!target) return
    fieldSearchRef.value?.blur?.()
    await nextTick()
    const scrollContainer = findScrollableContainer(editorBodyRef.value)
    const containerRect = scrollContainer.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const targetTop = scrollContainer.scrollTop + targetRect.top - containerRect.top
      - Math.max(0, (scrollContainer.clientHeight - targetRect.height) / 2)
    scrollContainer.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' })
    clearHighlight()
    target.classList.add('is-dialog-field-search-highlight')
    highlightedElement = target
    focusField(target)
    highlightTimer = window.setTimeout(clearHighlight, 1500)
  }

  onBeforeUnmount(clearHighlight)

  return {
    fieldSearchRef,
    fieldSearchKeyword,
    fetchFieldSuggestions,
    locateDialogField,
    clearFieldSearch,
  }
}
