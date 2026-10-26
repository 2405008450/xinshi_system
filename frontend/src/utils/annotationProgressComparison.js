import { businessDateTimeInputValue } from './dateTime.js'

export const progressTracks = [
  { key: 'project', label: '项目进度', hint: '状态流转与执行进展' },
  { key: 'customer', label: '客户进度', hint: '客户确认、反馈与需求' },
  { key: 'annotator', label: '标注员情况', hint: '人员安排、反馈与执行情况' },
]

export function compareProgressByDate(records) {
  const dates = new Map()
  const tracks = progressTracks.map(track => {
    const rows = (records[track.key] || []).map(row => ({
      ...row,
      businessTime: row.effectiveOn ? businessDateTimeInputValue(row.effectiveOn) : '',
      recordedTime: row.changedAt ? businessDateTimeInputValue(row.changedAt) : '',
    })).sort((a, b) => b.businessTime.localeCompare(a.businessTime) || b.recordedTime.localeCompare(a.recordedTime))
    for (const row of rows) {
      const day = row.businessTime.slice(0, 10) || '未标注时间'
      if (!dates.has(day)) dates.set(day, { day, project: [], customer: [], annotator: [] })
      dates.get(day)[track.key].push(row)
    }
    return { ...track, rows, latest: rows[0] || null }
  })
  const days = [...dates.values()].sort((a, b) => {
    if (a.day === '未标注时间') return 1
    if (b.day === '未标注时间') return -1
    return b.day.localeCompare(a.day)
  })
  return { tracks, days }
}
