const fieldKeys = new Set([
  'clientname', 'clientfullname', 'clientshortname', 'customername', 'customershortname',
  'subclientname', 'subclientshortname', 'parentclientname', 'parentclientshortname',
  'projectname', 'ordername', 'orderno', 'ordernumber', 'suborderno',
  'parentorderno', 'motherorderno', 'customerorderno', 'clientorderno',
  'consultationcode', 'sourcefilename',
])

export function isCopyableBusinessField(label, key = '') {
  const name = String(label || '').replace(/[\s：:*＊]/g, '')
  return /^(?:(?:母|子|当前|原|新|来源|关联|客户|三级|二级|内部|外部))*订单(?:号|编号)$/.test(name)
    || /^(?:(?:母|子|当前|原|新|来源|关联))*项目名称$/.test(name)
    || /^(?:(?:母|子|当前|原|新|来源|关联))*客户(?:名称|全称|简称)$/.test(name)
    || ['客户单号', '咨询编号', '客户单号/项目标识'].includes(name)
    || fieldKeys.has(String(key).replace(/[_\s-]/g, '').toLowerCase())
}

export function fieldCopyScope(target) {
  if (!target?.closest || target.closest('[data-field-copy="off"],.sensitive-contact-value,.chat-message-context-menu')) return null
  const marked = target.closest('td.app-field-copy-cell') || target.closest('[data-field-copy="true"]')
  if (marked) return marked
  // 编辑和只读表单，以及原生表格与详情小窗，沿用界面实际标签。
  const form = target.closest('.el-form-item')
  if (form && isCopyableBusinessField(form.querySelector('.el-form-item__label')?.textContent)) {
    return form.querySelector('.el-form-item__content') || form
  }
  const detail = target.closest('.el-descriptions__content')
  if (detail) {
    const label = detail.previousElementSibling?.classList.contains('el-descriptions__label')
      ? detail.previousElementSibling : detail.closest('td')?.querySelector('.el-descriptions__label')
    if(isCopyableBusinessField(label?.textContent))return detail
  }
  const identity = target.closest('.chat-order-identity__title,.chat-order-identity__number,.progress-dialog-project__order-no,.progress-dialog-order,.progress-compare-project-name,.progress-compare-identity>b,.source-project-name')
  if(identity)return identity
  const cell = target.closest('td')
  if (!cell) return null
  if (cell.classList.contains('el-descriptions__content')) {
    const label = cell.previousElementSibling?.classList.contains('el-descriptions__label')
      ? cell.previousElementSibling : cell.querySelector('.el-descriptions__label')
    return isCopyableBusinessField(label?.textContent) ? cell : null
  }
  const table = cell.closest('table')
  const headings = table?.querySelector('thead tr') || cell.closest('.el-table')?.querySelector('.el-table__header-wrapper tr')
  const sourceHeading = headings?.children[cell.cellIndex]
  const heading = (sourceHeading?.querySelector('.column-header-filter__label') || sourceHeading)?.cloneNode(true)
  heading?.querySelectorAll('button,[role="button"],[role="separator"],[role="slider"]').forEach(node=>node.remove())
  const label = heading?.textContent
  return isCopyableBusinessField(label) ? cell : null
}

const ignored = '.el-form-item__label,.el-form-item__error,.el-descriptions__label,.path-action-buttons,.inline-text-field__hint,.inline-text-field__actions,.el-input__suffix,.el-input__prefix,.el-input__count,.el-select__input,.el-tag__close,svg,[aria-hidden="true"],[data-field-copy-ignore]'

export function wholeFieldText(scope) {
  if (!scope) return ''
  const input = scope.matches('input,textarea') ? scope : scope.querySelector('input:not([type="hidden"]),textarea')
  if (input && !input.closest('.el-select,.el-autocomplete-suggestion')) return input.value || ''
  const clone = scope.cloneNode(true)
  clone.querySelectorAll(ignored).forEach(node => node.remove())
  clone.querySelectorAll('br').forEach(node => node.replaceWith('\n'))
  return clone.textContent?.trim() || ''
}

export function selectedFieldText(scope, target, selection = window.getSelection()) {
  if (target?.matches('input,textarea') && scope.contains(target)) {
    const { selectionStart: start, selectionEnd: end } = target
    if (Number.isInteger(start) && end > start) return target.value.slice(start, end)
  }
  if (!selection || selection.isCollapsed || !selection.rangeCount) return ''
  const range = selection.getRangeAt(0)
  return scope.contains(range.startContainer) && scope.contains(range.endContainer)
    ? selection.toString() : ''
}
