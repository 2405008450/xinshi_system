// Popper 监听锚点的滚动祖先，但窗口通过 left/top 移动时不会产生滚动。
// 使用定位引擎已有的 scroll 监听，兼容传送到 body 的选择框、日期及嵌套浮层。
// 不改变滚动位置，不派发 resize，避免触发业务页面的视口重排。
export function notifyWindowAnchors(root) {
  if (!root?.isConnected) return
  const viewport = root.ownerDocument.defaultView
  viewport?.dispatchEvent(new viewport.Event('scroll'))
}
