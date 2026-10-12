export const issueCategories = [
  { value: 'arrangement', label: '安排类' }, { value: 'execution', label: '执行类' },
  { value: 'problem', label: '问题类' }, { value: 'idea', label: '想法类' },
]
export const issueStatuses = [
  { value: 'pending', label: '未开始' }, { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' }, { value: 'cancelled', label: '已取消' },
]
export const issueCategoryLabel = value => issueCategories.find(x => x.value === value)?.label || '-'
export const issueStatusLabel = value => issueStatuses.find(x => x.value === value)?.label || '-'
export const issueColumns = [
  { key: 'content', label: '内容', width: 260 }, { key: 'category', label: '类别', width: 100 },
  { key: 'topic_path', label: '讨论主题', width: 210 },
  { key: 'source_title', label: '来源', width: 240 }, { key: 'proposer_name', label: '提出人', width: 120 },
  { key: 'task_count', label: '后续安排', width: 125 }, { key: 'executor_names', label: '执行人', width: 160 },
  { key: 'task_status_counts', label: '实际进度', width: 220 }, { key: 'remarks', label: '备注', width: 200 },
  { key: 'collected_by_name', label: '收录人', width: 120 }, { key: 'created_at', label: '收录时间', width: 180 },
  { key: 'updated_at', label: '更新时间', width: 180 },
]
export const defaultIssueColumns = ['content', 'category', 'topic_path', 'proposer_name', 'task_count', 'executor_names', 'task_status_counts']
export function cleanIssueColumns(value) {
  if (!Array.isArray(value)) throw new Error('字段设置格式无效')
  return [...new Set(value.filter(key => issueColumns.some(c => c.key === key)))]
}
export function issueParams(filters, pagination) {
  return {
    keyword: filters.keyword.trim() || undefined, category: filters.category || undefined,
    ...(filters.topic_id ? {topic_id:filters.topic_id} : {}),
    proposer_id: filters.proposer_id || undefined, executor_id: filters.executor_id || undefined,
    status: filters.status || undefined, planned_start: filters.range?.[0], planned_end: filters.range?.[1],
    skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit,
  }
}
export function issueStatusSummary(counts) {
  return issueStatuses.filter(s => counts?.[s.value]).map(s => `${s.label} ${counts[s.value]}`).join(' · ') || '-'
}
export const hongKongToday = (now = new Date()) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
export const issueDateLabel = value => value ? String(value).slice(0, 10).replace(/^(\d{4})-(\d{2})-(\d{2})$/, '$1年$2月$3日') : '-'
