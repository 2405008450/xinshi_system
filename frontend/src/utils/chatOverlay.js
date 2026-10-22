// 聊天窗口有独立层级，浮层必须高于触发它的窗口。
export function chatOverlayZIndex(element) {
  let top = 2100
  for (let node = element; node; node = node.parentElement) {
    top = Math.max(top, Number.parseInt(window.getComputedStyle(node).zIndex, 10) || 0)
  }
  return top + 10
}
