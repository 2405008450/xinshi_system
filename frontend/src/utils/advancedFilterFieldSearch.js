import { matchesSearch } from './searchMatching.js'

const FIELD_SELECTOR = '.compact-filter-cell, .el-form-item, [data-advanced-filter-label], .development-form-grid > div, .referral-advanced-grid > div, .team-advanced-grid > div, .channel-advanced-grid > div'
const HIDDEN_ATTRIBUTE = 'data-advanced-filter-search-hidden'

// 根据实际渲染的字段自动建索引，新增动态筛选字段无需另维护搜索清单。
export function collectAdvancedFilterFields(root) {
  if (!root) return []
  const fields = []
  for (const element of root.querySelectorAll(FIELD_SELECTOR)) {
    if (fields.some(field => field.element.contains(element))) continue
    let hidden = false
    for (let current = element; current && current !== root; current = current.parentElement) {
      if (current.style.display === 'none' || current.hidden) { hidden = true; break }
    }
    if (hidden) continue
    const label = element.getAttribute('data-advanced-filter-label') || element.querySelector(':scope > .el-form-item__label, :scope > .compact-filter-cell__label, :scope > label, :scope > span')?.textContent?.trim()
    if (!label) continue
    const column = element.closest('.el-col')
    const container = column && root.contains(column) && column.querySelectorAll('.el-form-item').length === 1 ? column : element
    fields.push({ element, container, label })
  }
  return fields
}

export function applyAdvancedFilterFieldSearch(fields, keyword) {
  for (const field of fields) {
    // 只隐藏呈现容器，不卸载控件、不改条件值，也不触发业务查询。
    if (matchesSearch(field.label, keyword)) field.container.removeAttribute(HIDDEN_ATTRIBUTE)
    else field.container.setAttribute(HIDDEN_ATTRIBUTE, '')
  }
}
