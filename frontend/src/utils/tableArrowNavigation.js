import { scrollFormTarget } from './formNavigation.js'

// grid[row][cell] 为该单元格内可导航的普通输入框；空数组表示跳过该格。
export function findTableArrowTarget(grid, row, cell, control, key) {
  const current = grid[row]?.[cell] || []
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    const step = key === 'ArrowLeft' ? -1 : 1
    if (current[control + step]) return current[control + step]
    for (let column = cell + step; column >= 0 && column < grid[row].length; column += step) {
      const controls = grid[row][column]
      if (controls.length) return step > 0 ? controls[0] : controls[controls.length - 1]
    }
  } else if (key === 'ArrowUp' || key === 'ArrowDown') {
    const step = key === 'ArrowUp' ? -1 : 1
    for (let index = row + step; index >= 0 && index < grid.length; index += step) {
      const controls = grid[index][cell] || []
      if (controls.length) return controls[Math.min(control, controls.length - 1)]
    }
  }
  return null
}

const excludedControls = '.el-select,.el-select-v2,.el-cascader,.el-autocomplete,.el-date-editor,.el-input-number,[role="combobox"]'
function canNavigate(control) {
  return control.matches('input:not([type]),input[type="text"],input[type="search"],input[type="tel"],input[type="email"],input[type="url"],textarea')
    && !control.disabled && !control.readOnly && !control.closest(excludedControls)
    && control.getClientRects().length > 0
}

export function handleTableArrowNavigation(event) {
  if (event.defaultPrevented || event.isComposing || event.keyCode === 229 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey
      || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
  const table = event.currentTarget, source = event.target
  if (!source?.matches?.('input,textarea') || !canNavigate(source) || source.closest('table') !== table) return
  const rows = Array.from(table.tBodies).flatMap(body => Array.from(body.rows))
  const row = rows.indexOf(source.closest('tr')), cell = source.closest('td')?.cellIndex
  if (row < 0 || cell == null) return
  const grid = rows.map(item => Array.from(item.cells).map(column => Array.from(column.querySelectorAll('input,textarea')).filter(canNavigate)))
  const index = grid[row][cell].indexOf(source)
  if (index < 0) return
  event.preventDefault()
  event.stopPropagation()
  const target = findTableArrowTarget(grid, row, cell, index, event.key)
  if (!target) return
  scrollFormTarget(target, table.parentElement, { behavior: 'auto', block: 'nearest', inline: 'center' })
  target.focus({ preventScroll: true })
  try { target.select() } catch { /* 个别输入类型不支持选择文本时仍保持焦点。 */ }
}
