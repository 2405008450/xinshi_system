export const DEFAULT_SCREENSHOT_SHORTCUT = 'Alt+KeyA'
const modifiers = ['Control', 'Alt', 'Shift', 'Meta']
export function shortcutFromEvent(event) {
  if (event.isComposing || event.repeat || !/^(Key[A-Z]|Digit[0-9]|F(?:[1-9]|1[0-2]))$/.test(event.code)) return null
  const keys = modifiers.filter((key, index) => event[['ctrlKey', 'altKey', 'shiftKey', 'metaKey'][index]])
  if (!keys.length) return null
  // 保留常见浏览器导航、关闭、刷新及编辑快捷键。
  if (keys.includes('Meta') || (keys.includes('Control') && /^(Key[ACVXZTWNRLPF]|Digit[0-9])$/.test(event.code)) || ['F5', 'F11', 'F12'].includes(event.code) || (keys.includes('Alt') && event.code === 'F4')) return null
  return [...keys, event.code].join('+')
}
export function shortcutLabel(value) {
  return value.replace('Control', 'Ctrl').replace(/Key([A-Z])|Digit([0-9])/g, (_, letter, digit) => letter || digit)
}
export function readScreenshotShortcut(storage, user) {
  try {
    const saved = storage.getItem(`screenshot-shortcut:${encodeURIComponent(user)}`)
    if (saved) {
      const parts = saved.split('+'), code = parts.pop()
      const event = { code, ctrlKey: parts.includes('Control'), altKey: parts.includes('Alt'), shiftKey: parts.includes('Shift'), metaKey: parts.includes('Meta') }
      if (shortcutFromEvent(event) === saved) return saved
    }
  } catch { /* 无法读取偏好时使用默认组合。 */ }
  return DEFAULT_SCREENSHOT_SHORTCUT
}
