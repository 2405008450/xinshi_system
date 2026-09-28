import { getLocalizedErrorMessage, getRawErrorDetail, safeUserMessage } from './errorMessages.js'

const camel = value => value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
const pathParts = value => Array.isArray(value)
  ? value.map(String)
  : typeof value === 'string' ? value.replace(/\[(\d+)\]/g, '.$1').split('.').filter(Boolean) : []
const pathKey = value => pathParts(value).map(camel).join('.')

/** 保留完整路径和明细索引；不以尾部字段名猜测目标，避免定位到错误行。 */
export function resolveServerFieldErrors(error, fields, aliases = {}) {
  const raw = getRawErrorDetail(error)
  const issues = Array.isArray(raw) ? raw.flatMap(item => {
    const parts = pathParts(item.loc)
    if (parts[0] !== 'body') return []
    return [{ path: parts.slice(1), message: item.msg }]
  }) : Array.isArray(raw?.fieldErrors) ? raw.fieldErrors : []
  const matches = []
  for (const issue of issues) {
    const original = pathParts(issue.path).join('.')
    const mapped = Object.prototype.hasOwnProperty.call(aliases, original) ? aliases[original] : original
    if (!mapped) continue
    const candidates = fields.filter(field => pathKey(field.prop) === pathKey(mapped))
    if (candidates.length !== 1) continue
    matches.push({ field: candidates[0], message: safeUserMessage(issue.message, '请检查此字段的填写内容') })
  }
  // 兼容旧接口标签定位，只接受唯一、完整匹配。
  if (!issues.length && typeof raw?.fieldLabel === 'string') {
    const candidates = fields.filter(field => field.label === raw.fieldLabel)
    if (candidates.length === 1) matches.push({ field: candidates[0], message: getLocalizedErrorMessage(error) })
  }
  return { matches, message: getLocalizedErrorMessage(error, '保存失败，请稍后重试') }
}
