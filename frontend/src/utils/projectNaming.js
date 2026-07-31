const padDatePart = (value) => String(value).padStart(2, '0')

export const formatProjectNameDate = (date = new Date()) =>
  `${String(date.getFullYear()).slice(-2)}${padDatePart(date.getMonth() + 1)}${padDatePart(date.getDate())}`

export const buildAutoProjectName = (
  clientShortName,
  subOrderCount = 0,
  date = new Date()
) => {
  const normalizedClientShortName = String(clientShortName || '').trim()
  if (!normalizedClientShortName) return ''

  const baseName = `${normalizedClientShortName}-${formatProjectNameDate(date)}`
  return subOrderCount > 0 ? `${baseName}-${subOrderCount}批` : baseName
}

export const isAutoProjectName = (projectName, clientShortName) => {
  const normalizedProjectName = String(projectName || '').trim()
  const normalizedClientShortName = String(clientShortName || '').trim()
  const prefix = `${normalizedClientShortName}-`
  if (!normalizedClientShortName || !normalizedProjectName.startsWith(prefix)) return false

  const suffix = normalizedProjectName.slice(prefix.length)
  if (/^\d{6}$/.test(suffix)) return true
  return /^\d{6}-\d+批$/.test(suffix)
}
