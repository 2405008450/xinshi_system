export const contactAvailabilityOptions = [
  { value: 'anytime', label: '随时可联系' },
  { value: 'morning', label: '上午' },
  { value: 'afternoon', label: '下午' },
  { value: 'evening', label: '晚间' },
  { value: 'weekday_daytime', label: '工作日白天' },
  { value: 'weekend', label: '周末' },
  { value: 'appointment', label: '需提前预约' },
]
export const contactAvailabilityLabel = value => contactAvailabilityOptions.find(item => item.value === value)?.label || value || '-'
