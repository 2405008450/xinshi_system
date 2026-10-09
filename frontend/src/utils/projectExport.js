export const PROJECT_EXPORT_TYPES = Object.freeze({
  PROJECTS: 'projects',
  RECONCILIATION: 'reconciliation',
  CLIENT_RECONCILIATION: 'client_reconciliation',
  TRANSLATOR_RECONCILIATION: 'translator_reconciliation',
  PERSONNEL_RECONCILIATION: 'personnel_reconciliation',
  CANDIDATE_TRACKING: 'candidate_tracking',
})

const commonTimeOptions = [
  { value: 'customer_consultation_time', label: '客户咨询时间' },
  { value: 'customer_confirmation_time', label: '客户确认时间' },
  { value: 'created_at', label: '创建时间' },
]

const modules = {
  translation: {
    name: '笔译项目',
    clientLabel: '客户',
    defaultTimeField: 'customer_reception_time',
    timeOptions: [
      { value: 'customer_reception_time', label: '客户接单时间' },
      { value: 'customer_deadline_time', label: '客户交稿时间' },
      { value: 'created_at', label: '创建时间' },
    ],
    projectHint: '继承当前全部筛选，导出所有匹配项目，不受分页和列表字段设置限制；Excel 包含母订单、子订单、子订单客户收费 3 个工作表。项目名称为真实文件名，子订单文件名称单独展示。',
    reconciliationHint: '将继承当前关键词和高级筛选；完整收费项进入“对账单”，缺少账单月份、税价或业务资料的记录进入“待补数据”。',
    fourthType: 'translator_reconciliation',
    fourthLabel: '导出译员对账单',
    fourthHint: '将继承当前关键词和高级筛选；仅导出已确认且未取消的当前有效译员安排，一位译员一行。',
  },
  interpretation: {
    name: '口译项目',
    timeOptions: [...commonTimeOptions, { value: 'scheduled_date', label: '预定日期' }],
    projectHint: '继承当前全部筛选，导出所有匹配项目及时间安排、语言方向、译员安排，不受分页和列表字段设置限制。',
    fourthType: 'translator_reconciliation',
    fourthLabel: '导出译员对账单',
    fourthHint: '仅导出当前未取消项目的译员安排；缺少结算依据的记录进入“待补数据”，不推算应付金额。',
  },
  annotation: {
    name: '标注项目',
    timeOptions: [...commonTimeOptions, { value: 'task_dispatched_at', label: '任务派发时间' }, { value: 'task_submitted_at', label: '任务提交时间' }],
    projectHint: '继承当前全部筛选；母单页包含命中母单及全部子单，子单页仅包含命中子单。导出语言项、客户单价、人员安排及自定义字段。',
    fourthType: 'personnel_reconciliation',
    fourthLabel: '导出人员对账单',
    fourthHint: '保留未取消人员安排的单价、币种、单位及已有工作量；缺少结算依据的记录进入“待补数据”，不使用试标报价或推算总额。',
  },
  recruitment: {
    name: '招聘项目',
    timeOptions: [...commonTimeOptions, { value: 'target_onboard_date', label: '目标入职日期' }],
    projectHint: '继承当前全部筛选，导出所有匹配项目、语言需求、项目进度、候选人及沟通和面试记录，不受分页限制。',
    fourthType: 'candidate_tracking',
    fourthLabel: '导出候选人跟进明细',
    fourthHint: '继承当前全部筛选，导出候选人阶段、推荐、面试、入职及跟进记录。',
  },
}

export function getProjectExportConfig(module) {
  const config = modules[module]
  if (!config) throw new Error(`未知项目导出模块：${module}`)
  const reconciliationHint = config.reconciliationHint || '继承当前全部筛选，保留预算、客户单价或服务费规则原值；缺少完整结算依据的记录进入“待补数据”，不推算结算金额。'
  return {
    ...config,
    module,
    defaultTimeField: config.defaultTimeField || 'customer_consultation_time',
    modes: [
      { type: 'projects', label: '导出项目 Excel', title: `导出${config.name}`, action: '导出 Excel', prefix: `${config.name}导出`, hint: config.projectHint },
      { type: 'reconciliation', label: '按时间导出客户对账单', title: `导出${config.name}客户对账单`, action: '导出客户对账单', prefix: `${config.name}${module === 'translation' ? '对账单' : '客户对账单'}`, hint: reconciliationHint },
      { type: 'client_reconciliation', label: '按客户导出客户对账单', title: `按客户导出${config.name}对账单`, action: '导出客户对账单', prefix: `${config.name}${module === 'translation' ? '对账单' : '客户对账单'}`, hint: `按所选${config.clientLabel || '母客户'}精确匹配，包含该${config.clientLabel || '母客户'}及其子客户的全部项目，不受当前列表筛选和时间范围限制。${module === 'translation' ? '' : '缺少结算依据的记录进入“待补数据”。'}` },
      { type: config.fourthType, label: config.fourthLabel, title: `导出${config.name}${config.fourthLabel.slice(2)}`, action: config.fourthLabel, prefix: `${config.name}${config.fourthLabel.slice(2)}`, hint: config.fourthHint },
    ],
  }
}

export function buildProjectExportParams(listParams, form, sort) {
  const { skip, limit, page, page_size, ...params } = listParams || {}
  let filters = {}
  try {
    const parsed = JSON.parse(params.field_filters || '{}')
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) filters = parsed
  } catch { /* 历史无效条件交由当前表单重新构造。 */ }
  const [dateStart, dateEnd] = form.dateRange || []
  filters[form.timeField] = { op: 'between', from: dateStart, to: dateEnd }
  return {
    ...params,
    keyword: params.keyword || undefined,
    field_filters: JSON.stringify(filters),
    sort: sort || params.sort || undefined,
    time_field: form.timeField,
    date_start: dateStart,
    date_end: dateEnd,
  }
}

export const buildClientReconciliationParams = (clientId) => ({ client_id: clientId })

export function buildProjectExportFilename(config, mode, form, clientLabel = '') {
  const safeText = (value) => String(value || '').trim().replace(/[\\/:*?"<>|]/g, '_')
  if (mode.type === 'client_reconciliation') return `${mode.prefix}_客户_${safeText(clientLabel || '客户')}.xlsx`
  const label = config.timeOptions.find((item) => item.value === form.timeField)?.label || '时间范围'
  const [start, end] = form.dateRange || []
  return `${mode.prefix}_${label}_${start}_至_${end}.xlsx`
}

export function downloadProjectWorkbook(blob, filename) {
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    // 给浏览器下载任务一个事件循环完成接管，再释放临时 URL。
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }
}
