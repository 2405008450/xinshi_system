const OPEN_NON_PROJECT_STATUSES = new Set(['pending', 'in_progress'])
const TERMINAL_PROJECT_STATUSES = new Set(['completed', 'cancelled', 'partially_cancelled', 'terminated'])

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
  return !TERMINAL_PROJECT_STATUSES.has(item?.project_status || item?.status)
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
