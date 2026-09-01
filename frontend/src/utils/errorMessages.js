const FIELD_LABELS = {
  username: '用户名',
  password: '密码',
  email: '邮箱',
  client_id: '客户',
  client_name: '客户名称',
  client_short_name: '客户简称',
  contact_id: '联系人',
  contact_name: '联系人',
  consultation_type: '咨询类型',
  consultation_time: '咨询时间',
  consultation_method: '咨询方式',
  consultation_description: '咨询描述',
  project_name: '项目名称',
  project_type: '项目类型',
  project_types: '项目类型',
  locations: '地点',
  time_ranges: '预定时段',
  scheduled_start: '开始时间',
  scheduled_end: '结束时间',
  language_pair: '翻译方向',
  language_directions: '语言方向',
  language_items: '语言范围',
  task_description: '具体任务',
  position_title: '职位名称/类型',
  headcount_min: '招聘人数',
  headcount_max: '招聘人数上限',
  employment_range: '拟履职周期',
  work_location: '工作地点',
  user_id: '用户',
  role_id: '角色',
  project_id: '项目',
  translator_id: '译员',
  status: '状态',
  name: '名称',
  phone: '联系电话',
  start_date: '开始日期',
  end_date: '结束日期',
  start_time: '开始时间',
  end_time: '结束时间'
}

const STATUS_FALLBACKS = {
  400: '请求内容有误，请检查后重试',
  401: '登录状态已失效，请重新登录',
  403: '没有权限执行此操作',
  404: '请求的内容不存在或已被删除',
  408: '请求超时，请稍后重试',
  409: '数据状态已发生变化，请刷新后重试',
  422: '提交内容校验失败，请检查后重试',
  429: '操作过于频繁，请稍后重试',
  500: '服务暂时异常，请稍后重试',
  502: '上游服务暂时不可用，请稍后重试',
  503: '服务暂时不可用，请稍后重试'
}

const hasChinese = (value) => /[\u3400-\u9fff]/.test(value)
const hasEnglishWord = (value) => /[A-Za-z]{2,}/.test(value)
const hasTechnicalDetail = (value) => /(?:axios|pydantic|sqlalchemy|integrityerror|operationalerror|traceback|validationerror|field required|network error|request failed with status code|timeout of \d+ms exceeded|\b(?:select|insert|update|delete)\b[^\n]*(?:from|into|set|where))/i.test(value)

export function fieldLabelFromLocation(location) {
  if (!Array.isArray(location)) return '相关字段'
  const field = [...location]
    .reverse()
    .find((part) => typeof part === 'string' && !['body', 'query', 'path', 'header'].includes(part))
  return FIELD_LABELS[field] || '相关字段'
}

const validationMessageByType = (item, label) => {
  const type = String(item?.type || '')
  const context = item?.ctx || {}
  if (type === 'missing') return `${label}为必填项`
  if (type.includes('string_too_short')) return `${label}不能少于 ${context.min_length ?? context.minLength ?? 1} 个字符`
  if (type.includes('string_too_long')) return `${label}不能超过 ${context.max_length ?? context.maxLength ?? ''} 个字符`
  if (type.includes('greater_than_equal')) return `${label}不能小于 ${context.ge ?? context.limit_value ?? ''}`
  if (type.includes('greater_than')) return `${label}必须大于 ${context.gt ?? context.limit_value ?? ''}`
  if (type.includes('less_than_equal')) return `${label}不能大于 ${context.le ?? context.limit_value ?? ''}`
  if (type.includes('less_than')) return `${label}必须小于 ${context.lt ?? context.limit_value ?? ''}`
  if (type.includes('date') || type.includes('datetime')) return `${label}的日期时间格式不正确`
  if (type.includes('uuid')) return `${label}标识无效`
  if (type.includes('email')) return `${label}格式不正确`
  if (type.includes('list') || type.includes('array')) return `${label}应为有效列表`
  if (type.includes('int') || type.includes('float') || type.includes('decimal') || type.includes('number')) return `${label}应为有效数字`
  if (type.includes('bool')) return `${label}应为有效状态值`
  if (type.includes('literal') || type.includes('enum')) return `${label}的选项无效`
  return `${label}内容格式不正确`
}

export function formatValidationErrors(errors) {
  if (!Array.isArray(errors) || !errors.length) return STATUS_FALLBACKS[422]
  return errors.map((item) => {
    const label = fieldLabelFromLocation(item?.loc)
    const message = String(item?.msg || '').trim()
    return hasChinese(message) ? `${label}：${message}` : validationMessageByType(item, label)
  }).join('；')
}

export function statusFallback(status, fallback = '操作失败，请稍后重试') {
  return STATUS_FALLBACKS[Number(status)] || fallback
}

export function safeUserMessage(value, fallback) {
  if (typeof value !== 'string') return fallback
  const message = value.trim()
  if (!message) return fallback
  if (hasTechnicalDetail(message)) return fallback
  if (hasEnglishWord(message) && !hasChinese(message)) return fallback
  return message
}

export function getLocalizedErrorMessage(error, fallback = '操作失败，请稍后重试') {
  const status = error?.response?.status
  const resolvedFallback = statusFallback(status, fallback)
  const rawDetail = error?.rawDetail ?? error?.response?.data?.detail ?? error?.detail
  if (Array.isArray(rawDetail)) return formatValidationErrors(rawDetail)
  if (rawDetail && typeof rawDetail === 'object') {
    return safeUserMessage(rawDetail.message, resolvedFallback)
  }
  return safeUserMessage(rawDetail, safeUserMessage(error?.message, resolvedFallback))
}

export function normalizeApiError(error) {
  const rawDetail = error?.response?.data?.detail ?? error?.detail
  const isNetworkError = !error?.response && (
    error?.code === 'ERR_NETWORK' || /network error/i.test(String(error?.message || ''))
  )
  const isTimeoutError = !error?.response && (
    ['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code) || /timeout/i.test(String(error?.message || ''))
  )
  const fallback = isTimeoutError
    ? '请求超时，请稍后重试'
    : isNetworkError
      ? '网络异常，请检查网络后重试'
      : statusFallback(error?.response?.status, '请求失败，请稍后重试')
  const detail = Array.isArray(rawDetail)
    ? formatValidationErrors(rawDetail)
    : getLocalizedErrorMessage({ ...error, rawDetail }, fallback)

  error.rawDetail = rawDetail
  error.detail = detail
  error.message = detail
  if (error.response?.data && Object.prototype.hasOwnProperty.call(error.response.data, 'detail')) {
    error.response.data.detail = detail
  }
  return error
}

export function installChineseMessageGuard(messageService) {
  const fallbacks = {
    error: '操作失败，请稍后重试',
    warning: '请检查输入内容后重试'
  }
  Object.entries(fallbacks).forEach(([method, fallback]) => {
    const original = messageService?.[method]
    if (typeof original !== 'function' || original.__chineseMessageGuard) return
    const guarded = (options, ...args) => {
      if (typeof options === 'string') {
        return original(safeUserMessage(options, fallback), ...args)
      }
      if (options && typeof options === 'object' && typeof options.message === 'string') {
        return original({ ...options, message: safeUserMessage(options.message, fallback) }, ...args)
      }
      return original(options, ...args)
    }
    guarded.__chineseMessageGuard = true
    messageService[method] = guarded
  })
}

export { FIELD_LABELS, STATUS_FALLBACKS }
