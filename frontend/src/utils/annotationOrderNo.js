const ANNOTATION_ORDER_NO_PATTERN = /^AP-[A-Z0-9][A-Z0-9._-]*$/

export const normalizeAnnotationOrderNo = value => String(value || '').trim().toUpperCase()

export const isValidAnnotationOrderNo = value => {
  const normalized = normalizeAnnotationOrderNo(value)
  return normalized.length <= 50 && ANNOTATION_ORDER_NO_PATTERN.test(normalized)
}
