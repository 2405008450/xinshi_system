export const interpretationRatingOptions = ['一星', '二星', '三星', '四星', '五星', '六星']
  .map((label, index) => ({ value: index + 1, label }))

export const interpretationRatingLabel = value => interpretationRatingOptions.find(item => item.value === value)?.label || '-'
export const interpretationRatingHint = '四星以上为可担任大型会议交传与同传'
