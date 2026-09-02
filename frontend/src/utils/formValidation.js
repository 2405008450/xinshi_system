const ERROR_ITEM_SELECTOR = '.el-form-item.is-error'

const FOCUSABLE_CONTROL_SELECTOR = [
  // el-select 的可交互外壳位于内部 input 之前，直接聚焦外壳在编辑态更稳定。
  '.el-select__wrapper:not(.is-disabled)',
  // Element Plus 的选择器、日期控件内部输入框通常带 readonly，但仍可接收焦点。
  'input:not([disabled])',
  'textarea:not([disabled]):not([readonly])',
  'select:not([disabled])',
  'button:not([disabled])',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * 将视图定位到表单内第一个校验失败项，并聚焦其中可编辑的控件。
 *
 * @param {Element | null | undefined} formElement Element Plus 表单根元素
 * @param {ScrollIntoViewOptions} scrollOptions 滚动参数
 * @returns {boolean} 是否找到了错误字段
 */
export function focusFirstInvalidField(
  formElement,
  scrollOptions = { behavior: 'smooth', block: 'center', inline: 'nearest' },
) {
  const errorItem = formElement?.querySelector?.(ERROR_ITEM_SELECTOR)
  if (!errorItem) return false

  errorItem.scrollIntoView?.(scrollOptions)

  const control = errorItem.querySelector?.(FOCUSABLE_CONTROL_SELECTOR)
  if (control?.getAttribute?.('aria-disabled') !== 'true') {
    const focusControl = () => {
      control?.focus?.({ preventScroll: true })
    }
    // 点击提交按钮后可能紧接着发生 loading 重渲染，下一帧聚焦可避免焦点被按钮卸载覆盖。
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(focusControl)
    } else {
      focusControl()
    }
  }

  return true
}

export { ERROR_ITEM_SELECTOR, FOCUSABLE_CONTROL_SELECTOR }
