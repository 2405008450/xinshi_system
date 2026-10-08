export function formatOverviewDate(value) {
  if (!value) return '-'
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/)
  return match ? `${match[1]}年${Number(match[2])}月${Number(match[3])}日` : String(value)
}

export function formatOverviewOperationTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Hong_Kong', year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date)
}

export const overviewOperationLabels = {
  languageEdit: '修改语种计划/备注', groupCreate: '新增群', groupEdit: '修改群资料',
  countRegister: '登记人数', countVoid: '作废人数', archive: '归档群', restore: '恢复群',
  language_edit: '修改语种计划/备注', group_create: '新增群', group_edit: '修改群资料',
  count_register: '登记人数', count_void: '作废人数',
}
const fieldLabels = {
  name: '群名', isBuilt: '是否已建', builtDate: '建群日期', plan: '计划', remarks: '备注',
  archived: '归档', countId: '登记编号', statisticsDate: '统计日期', peopleCount: '人数', voidReason: '作废原因',
}
export function formatOverviewChange(values = {}) {
  return Object.entries(values).map(([key, value]) => {
    const display = typeof value === 'boolean' ? (value ? '是' : '否')
      : /Date$/.test(key) ? formatOverviewDate(value) : (value === null || value === '' ? '-' : String(value))
    return `${fieldLabels[key] || key}：${display}`
  }).join('\n') || '-'
}

export function formatOverviewCount(value) {
  return value === null || value === undefined ? '-' : Number(value).toLocaleString('zh-CN')
}

export function todayOverviewDate() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
}
