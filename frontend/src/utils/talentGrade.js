export const talentGradeOptions = [
  { value: 'S', label: 'S' },
  { value: 'A', label: 'A' },
  { value: 'B', label: 'B' },
  { value: 'C', label: 'C' },
  { value: 'pending', label: '待评定' },
]

export const talentGradeLabel = value => talentGradeOptions.find(item => item.value === value)?.label || '待评定'
