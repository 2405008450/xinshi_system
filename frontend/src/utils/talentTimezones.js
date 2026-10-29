// 15 分钟步长涵盖半小时、45 分钟偏移，支持按 UTC+8 等文本搜索。
export const talentTimezoneOptions = Array.from({ length: 105 }, (_, index) => {
  const total = -720 + index * 15
  const minutes = Math.abs(total) % 60
  const value = `UTC${total < 0 ? '-' : '+'}${Math.floor(Math.abs(total) / 60)}${minutes ? `:${String(minutes).padStart(2, '0')}` : ''}`
  return { value, label: value }
})
