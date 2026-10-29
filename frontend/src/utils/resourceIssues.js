export const issueCategories = [
  { value: 'arrangement', label: '信息同步' }, { value: 'request', label: '提出需求' },
  { value: 'idea', label: '想法讨论' }, { value: 'decision', label: '决策批复' },
  { value: 'execution', label: '任务执行' }, { value: 'problem', label: '问题/异常' },
  { value: 'risk', label: '风险隐患' }, { value: 'standard', label: '规则标准' },
]
export const issueStatuses = [
  { value: 'pending', label: '未开始' }, { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' }, { value: 'cancelled', label: '已取消' },
]
export const issueCategoryLabel = value => issueCategories.find(x => x.value === value)?.label || '-'
export const issueStatusLabel = value => issueStatuses.find(x => x.value === value)?.label || '-'
export const issueColumns = [
  { key: 'content', label: '内容', width: 260 }, { key: 'category', label: '类别', width: 100 },
  { key: 'specific_classification', label: '具体分类', width: 160 },
  { key: 'source_title', label: '来源', width: 240 }, { key: 'proposer_name', label: '提出人', width: 120 },
  { key: 'executor_names', label: '跟进人', width: 160 }, { key: 'planned_completion_at', label: '预定完成时间', width: 180 },
  { key: 'actual_progress', label: '实际进度', width: 220 }, { key: 'notify_department_names', label: '同步部门', width: 160 },
  { key: 'notify_user_names', label: '同步人员', width: 160 }, { key: 'remarks', label: '备注', width: 200 },
  { key: 'notified_user_names', label: '谁被通知', width: 180 },
  { key: 'collected_by_name', label: '保存人', width: 120 }, { key: 'created_at', label: '保存时间', width: 180 },
  { key: 'updated_at', label: '更新时间', width: 180 },
]
export const defaultIssueColumns = ['content', 'category', 'specific_classification', 'proposer_name', 'collected_by_name', 'notified_user_names', 'executor_names', 'planned_completion_at', 'actual_progress', 'created_at']
export function cleanIssueColumns(value) {
  if (!Array.isArray(value)) throw new Error('字段设置格式无效')
  return [...new Set(value.filter(key => issueColumns.some(c => c.key === key)))]
}
export function issueParams(filters, pagination) {
  return {
    keyword: filters.keyword.trim() || undefined, category: filters.category || undefined,
    ...(filters.topic_id ? {topic_id:filters.topic_id} : {}),
    ...(filters.notified_me ? {notified_me:true} : {}), ...(filters.created_by_me ? {created_by_me:true} : {}),
    proposer_id: filters.proposer_id || undefined, executor_id: filters.executor_id || undefined,
    status: filters.status || undefined, planned_start: filters.range?.[0], planned_end: filters.range?.[1],
    ...(filters.department_id?{department_id:filters.department_id}:{}),...(filters.saved_range?{saved_start:filters.saved_range[0],saved_end:filters.saved_range[1]}:{}),
    skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit,
  }
}
export function issueStatusSummary(counts) {
  return issueStatuses.filter(s => counts?.[s.value]).map(s => `${s.label} ${counts[s.value]}`).join(' · ') || '-'
}
export const hongKongToday = (now = new Date()) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
export const issueDateLabel = value => value ? String(value).slice(0, 10).replace(/^(\d{4})-(\d{2})-(\d{2})$/, '$1年$2月$3日') : '-'
