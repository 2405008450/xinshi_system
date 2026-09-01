const padDatePart = (value) => String(value).padStart(2, '0')

export const formatProjectNameDate = (date = new Date()) =>
  `${String(date.getFullYear()).slice(-2)}${padDatePart(date.getMonth() + 1)}${padDatePart(date.getDate())}`

export const formatProjectNameDeadline = (value) => {
  if (!value) return ''
  // Element Plus 提交的是本地时间字符串，优先直接拆分，避免 Date 带来的时区偏移。
  const matched = String(value).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  if (matched) return `${Number(matched[2])}月${Number(matched[3])}日${Number(matched[4])}点`

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1}月${date.getDate()}日${date.getHours()}点`
}

const projectNameLanguageAliases = new Map([
  ['中文', '中'], ['英语', '英'], ['西班牙语', '西'], ['葡萄牙语', '葡'],
  ['法语', '法'], ['德语', '德'], ['意大利语', '意'], ['荷兰语', '荷'],
  ['俄语', '俄'], ['乌克兰语', '乌克兰'], ['波兰语', '波兰'], ['捷克语', '捷克'],
  ['斯洛伐克语', '斯洛伐克'], ['匈牙利语', '匈'], ['罗马尼亚语', '罗'],
  ['保加利亚语', '保'], ['塞尔维亚语', '塞'], ['希腊语', '希腊'],
  ['土耳其语', '土'], ['瑞典语', '瑞'], ['丹麦语', '丹'], ['挪威语', '挪'],
  ['芬兰语', '芬'], ['冰岛语', '冰'], ['日语', '日'], ['韩语', '韩'],
  ['越南语', '越'], ['泰语', '泰'], ['印度尼西亚语', '印尼'], ['马来语', '马来'],
  ['印地语', '印地'], ['孟加拉语', '孟加拉'], ['阿拉伯语', '阿'],
  ['希伯来语', '希伯来'], ['波斯语', '波斯'], ['乌尔都语', '乌尔都'],
  ['哈萨克语', '哈'], ['蒙古语', '蒙'], ['藏语', '藏'], ['缅甸语', '缅'],
  ['高棉语', '高棉'], ['老挝语', '老挝'],
])

const compactProjectNameLanguage = (value) => {
  const normalized = String(value || '').trim().replace(/[（(].*?[）)]/g, '')
  return projectNameLanguageAliases.get(normalized)
    || normalized.replace(/[语文]$/, '')
}

export const formatProjectNameLanguagePair = (value) => String(value || '')
  .split(/[；;,，\n]+/)
  .map((item) => item.trim())
  .filter(Boolean)
  .map((item) => {
    const parts = item.split(/\s*(?:→|->|=>)\s*/)
    if (parts.length !== 2) return item
    return `${compactProjectNameLanguage(parts[0])}译${compactProjectNameLanguage(parts[1])}`
  })
  .join('、')

export const buildAutoProjectName = (
  clientShortName,
  subOrderCount = 0,
  _date = new Date(),
  languagePair = '',
  customerDeadlineTime = ''
) => {
  const normalizedClientShortName = String(clientShortName || '').trim()
  if (!normalizedClientShortName) return ''

  const normalizedLanguagePair = formatProjectNameLanguagePair(languagePair)
  const deadlineText = formatProjectNameDeadline(customerDeadlineTime)
  const parts = [normalizedClientShortName]
  if (normalizedLanguagePair) parts.push(normalizedLanguagePair)
  if (deadlineText) parts.push(`${deadlineText}回稿`)
  if (!normalizedLanguagePair && !deadlineText) parts.push(formatProjectNameDate(_date))
  if (normalizedLanguagePair || deadlineText) {
    const baseName = parts.join('，')
    return subOrderCount > 0 ? `${baseName}，${subOrderCount}批` : baseName
  }
  const baseName = parts.join('-')
  return subOrderCount > 0 ? `${baseName}-${subOrderCount}批` : baseName
}

export const isAutoProjectName = (projectName, clientShortName) => {
  const normalizedProjectName = String(projectName || '').trim()
  const normalizedClientShortName = String(clientShortName || '').trim()
  if (!normalizedClientShortName) return false

  const currentPrefix = `${normalizedClientShortName}，`
  if (normalizedProjectName.startsWith(currentPrefix)) {
    const suffix = normalizedProjectName.slice(currentPrefix.length)
    return /^.+，\d{1,2}月\d{1,2}日\d{1,2}点回稿(?:，\d+批)?$/.test(suffix)
  }

  const prefix = `${normalizedClientShortName}-`
  if (!normalizedProjectName.startsWith(prefix)) return false
  const suffix = normalizedProjectName.slice(prefix.length)
  if (/^.+-\d{8}-\d{2}:?\d{2}回(?:-\d+批)?$/.test(suffix)) return true
  if (/^\d{6}$/.test(suffix)) return true
  if (/^\d{6}-\d+批$/.test(suffix)) return true
  return /^\d{6}-.+-\d{8}-\d{2}:?\d{2}回稿(?:-\d+批)?$/.test(suffix)
}
