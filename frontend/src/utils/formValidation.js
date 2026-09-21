import {
  DEFAULT_SCROLL_OPTIONS,
  FORM_CONTROL_SELECTOR,
  focusFormTarget,
  revealFormTarget,
  scrollFormTarget,
} from './formNavigation.js'

const ERROR_ITEM_SELECTOR = '.el-form-item.is-error'
const FOCUSABLE_CONTROL_SELECTOR = FORM_CONTROL_SELECTOR

/**
 * 将视图定位到表单内第一个校验失败项，并聚焦其中可编辑的控件。
 *
 * @param {Element | null | undefined} formElement Element Plus 表单根元素
 * @param {ScrollIntoViewOptions} scrollOptions 滚动参数
 * @returns {boolean} 是否找到了错误字段
 */
export async function focusFirstInvalidField(
  formElement,
  scrollOptions = DEFAULT_SCROLL_OPTIONS,
) {
  const errorItem = formElement?.querySelector?.(ERROR_ITEM_SELECTOR)
  if (!errorItem) return false

  await revealFormTarget(errorItem)
  scrollFormTarget(errorItem, formElement, scrollOptions)
  focusFormTarget(errorItem)

  return true
}

export { ERROR_ITEM_SELECTOR, FOCUSABLE_CONTROL_SELECTOR }
