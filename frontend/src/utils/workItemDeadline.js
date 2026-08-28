const OPEN_NON_PROJECT_STATUSES = new Set(['pending', 'in_progress'])
// 这些状态下客户交稿节点已经完成或项目已经结束，不再触发整行逾期/紧急高亮。
// 同时保留旧状态别名，兼容工作台历史数据尚未完成状态迁移的情况。
const RELEASED_PROJECT_DEADLINE_STATUSES = new Set([
  'completed',
  'sent_to_client',
  'client_feedback',
  'feedback_sent_to_client',
  'ended',
  'settled',
  'closed',
  'consultation_no_result',
  'resource_sourcing_cancelled',
  'trial_failed',
  'cancelled',
  'partially_cancelled',
  'terminated'
])

export const DEADLINE_STATE = Object.freeze({
  OVERDUE: 'overdue',
  URGENT: 'urgent',
  NORMAL: 'normal'
})

export function getWorkItemDeadline(item) {
  if (item?.source_type === 'non_project') {
    return item?.planned_completion_at ?? null
  }
  return item?.customer_deadline_time ?? item?.customerDeadlineTime ?? null
}

export function isWorkItemOpen(item) {
  if (item?.source_type === 'non_project') {
    return OPEN_NON_PROJECT_STATUSES.has(item?.status)
  }
  const status = String(item?.project_status || item?.status || '').trim()
  return !RELEASED_PROJECT_DEADLINE_STATUSES.has(status)
}

export function getWorkItemDeadlineState(item, now = new Date()) {
  if (!isWorkItemOpen(item)) return DEADLINE_STATE.NORMAL

  const rawDeadline = getWorkItemDeadline(item)
  if (!rawDeadline) return DEADLINE_STATE.NORMAL

  const deadline = new Date(rawDeadline)
  const reference = now instanceof Date ? now : new Date(now)
  if (Number.isNaN(deadline.getTime()) || Number.isNaN(reference.getTime())) {
    return DEADLINE_STATE.NORMAL
  }
  if (deadline < reference) return DEADLINE_STATE.OVERDUE
  if (deadline.getTime() <= reference.getTime() + 24 * 60 * 60 * 1000) {
    return DEADLINE_STATE.URGENT
  }
  return DEADLINE_STATE.NORMAL
}

export function compareWorkItemsByDeadline(left, right, now = new Date()) {
  const rank = {
    [DEADLINE_STATE.OVERDUE]: 0,
    [DEADLINE_STATE.URGENT]: 1,
    [DEADLINE_STATE.NORMAL]: 2
  }
  const stateDifference = rank[getWorkItemDeadlineState(left, now)] - rank[getWorkItemDeadlineState(right, now)]
  if (stateDifference) return stateDifference

  const leftTime = new Date(getWorkItemDeadline(left) || '').getTime()
  const rightTime = new Date(getWorkItemDeadline(right) || '').getTime()
  if (Number.isNaN(leftTime) && Number.isNaN(rightTime)) return 0
  if (Number.isNaN(leftTime)) return 1
  if (Number.isNaN(rightTime)) return -1
  return leftTime - rightTime
}
