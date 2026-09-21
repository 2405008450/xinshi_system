import { nextTick, onBeforeUnmount, ref } from 'vue'
import {
  focusFormTarget,
  revealFormTarget,
  scrollFormTarget,
} from '@/utils/formNavigation'

const normalize = (value) => String(value || '').toLocaleLowerCase().replace(/\s+/g, '')

const directText = (element) => {
  if (!element) return ''
  return Array.from(element.childNodes)
    .filter((node) => node.nodeType === 3)
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
  const group = formItem.closest(
    '.repeat-card, .price-card, .interpreter-requirement-group, [data-dialog-field-search-group]',
  )
  if (!group) return ''
  const heading = group.querySelector(
    '.repeat-title, .requirement-group-title, [data-dialog-field-search-group-title]',
  )
  return directText(heading) || heading?.textContent?.trim() || ''
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
    const targets = Array.from(root.querySelectorAll(
      '.el-form-item, [data-dialog-field-search-label]',
    )).filter((element) => (
      element.matches('.el-form-item')
      || !element.closest('.el-form-item')
    ))
    return targets.flatMap((element, index) => {
      const labelElement = element.querySelector(':scope > .el-form-item__label, :scope > label.el-form-item__label')
      const label = (
        element.dataset.dialogFieldSearchLabel
        || labelElement?.textContent
        || ''
      ).trim().replace(/[：:]$/, '')
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
        aliases: (element.dataset.dialogFieldSearchAliases || '').split(/[，,、|]/).map((value) => value.trim()).filter(Boolean),
        location: [section, group].filter(Boolean).join(' · '),
      }]
    })
  }

  const scoreField = (item, keyword) => {
    const label = normalize(item.searchLabel)
    const aliases = (item.aliases || []).map(normalize)
    const location = normalize(item.location)
    if (label === keyword) return 0
    if (aliases.some((value) => value === keyword)) return 1
    if (label.startsWith(keyword)) return 2
    if (aliases.some((value) => value.startsWith(keyword))) return 3
    if (label.includes(keyword)) return 4
    if (aliases.some((value) => value.includes(keyword))) return 5
    if (location.includes(keyword)) return 6
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

  const locateDialogField = async (item) => {
    let target = suggestionTargets.get(item?.key)
    if (!target?.isConnected) {
      collectFields()
      target = suggestionTargets.get(item?.key)
    }
    if (!target) return false
    fieldSearchRef.value?.blur?.()
    await nextTick()
    await revealFormTarget(target)
    scrollFormTarget(target, editorBodyRef.value)
    clearHighlight()
    target.classList.add('is-dialog-field-search-highlight')
    highlightedElement = target
    focusFormTarget(target)
    highlightTimer = window.setTimeout(clearHighlight, 1500)
    return true
  }

  const locateDialogFieldByLabel = async (label, occurrence = 1) => {
    const normalizedLabel = normalize(label)
    const matches = collectFields().filter((item) => normalize(item.searchLabel).includes(normalizedLabel))
    return await locateDialogField(matches[Math.max(0, occurrence - 1)])
  }

  onBeforeUnmount(clearHighlight)

  return {
    fieldSearchRef,
    fieldSearchKeyword,
    fetchFieldSuggestions,
    locateDialogField,
    locateDialogFieldByLabel,
    clearFieldSearch,
  }
}
