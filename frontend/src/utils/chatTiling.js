export const tileLimit = mode => mode === 'medium' ? 3 : 6

export function chatTileLayout(count, mode, width, height) {
  const gap = 10, availableWidth = Math.max(1, width - 20), availableHeight = Math.max(1, height - 70)
  const minimumWidth = mode === 'medium' ? 520 : 320
  const columns = Math.max(1, Math.min(count || 1, 3, Math.floor((availableWidth + gap) / (minimumWidth + gap))))
  const rows = Math.ceil(Math.max(1, count) / columns)
  // 小屏保留可用的输入区和消息区，多余窗口在平铺区域内滚动。
  const rowHeight = Math.max(400, Math.floor((availableHeight - gap * (rows - 1)) / rows))
  return { columns, rows, rowHeight }
}
