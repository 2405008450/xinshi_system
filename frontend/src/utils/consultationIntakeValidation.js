export function interpretationTimeRangesError(value) {
  if (!Array.isArray(value) || !value.length) return '请至少保留一个预定时段'
  if (value.some((item) => !item?.scheduled_start || !item?.scheduled_end)) {
    return '请填写完整的预定时段'
  }
  if (value.some((item) => Date.parse(item.scheduled_end) < Date.parse(item.scheduled_start))) {
    return '预定结束时间不能早于预定开始时间'
  }
  return ''
}

export function interpretationDirectionsError(value) {
  if (!Array.isArray(value) || !value.length) return '请选择口译方向'
  if (value.some((item) => !item?.source_language_id || !item?.target_language_id)) {
    return '请选择完整的口译方向'
  }
  if (value.some((item) => item.source_language_id === item.target_language_id)) {
    return '同一口译方向内的语种不能重复'
  }
  const directionKeys = value.map((item) => (
    [item.source_language_id, item.target_language_id].sort().join(':')
  ))
  if (new Set(directionKeys).size !== directionKeys.length) return '同一双向口译方向不能重复'
  if (value.some((item) => !Number.isInteger(item?.required_count) || item.required_count < 1)) {
    return '请为每个口译方向填写大于等于 1 的需求人数'
  }
  return ''
}
