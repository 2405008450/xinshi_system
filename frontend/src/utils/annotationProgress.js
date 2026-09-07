const progressTimestamp = (row) => `${row.effectiveOn || ''}|${row.changedAt || ''}`

export const groupAnnotationProgressRows = (rows = [], currentStatus = '') => {
  const statusRows = rows.filter((row) => row.fromStatus !== row.toStatus)
  const groups = statusRows.map((row) => ({
    key: `stage:${row.id}`,
    id: row.id,
    status: row.toStatus,
    fromStatus: row.fromStatus,
    effectiveOn: row.effectiveOn,
    changedAt: row.changedAt,
    changedByName: row.changedByName,
    synthetic: false,
    children: row.changeNote
      ? [{ ...row, key: `status-note:${row.id}`, kind: 'status-note' }]
      : [],
  }))
  const syntheticByStatus = new Map()

  rows.filter((row) => row.fromStatus === row.toStatus).forEach((row) => {
    const candidates = groups
      .filter((group) => group.status === row.toStatus && String(group.effectiveOn || '') <= String(row.effectiveOn || ''))
      .sort((left, right) => progressTimestamp(right).localeCompare(progressTimestamp(left)))
    let parent = candidates[0]
    if (!parent) {
      parent = syntheticByStatus.get(row.toStatus)
      if (!parent) {
        parent = {
          key: `synthetic:${row.toStatus}`,
          status: row.toStatus,
          fromStatus: null,
          effectiveOn: row.effectiveOn,
          changedAt: row.changedAt,
          changedByName: null,
          synthetic: true,
          children: [],
        }
        syntheticByStatus.set(row.toStatus, parent)
        groups.push(parent)
      } else if (progressTimestamp(row) > progressTimestamp(parent)) {
        parent.effectiveOn = row.effectiveOn
        parent.changedAt = row.changedAt
      }
    }
    if (row.changeNote) {
      parent.children.push({ ...row, key: `progress:${row.id}`, kind: 'progress' })
    }
  })

  groups.forEach((group) => {
    group.children.sort((left, right) => progressTimestamp(right).localeCompare(progressTimestamp(left)))
  })
  groups.sort((left, right) => progressTimestamp(right).localeCompare(progressTimestamp(left)))
  const currentGroup = groups.find((group) => group.status === currentStatus)
  if (currentGroup) currentGroup.isCurrent = true
  return groups
}
