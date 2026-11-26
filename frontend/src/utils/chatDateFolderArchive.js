export const ARCHIVE_DATE_FOLDER_DAYS = 30

const MS_PER_DAY = 86400000
const HK_OFFSET_MS = 8 * 3600 * 1000

export function businessTodayDayIndex(now = new Date()) {
  const hk = new Date(now.getTime() + HK_OFFSET_MS)
  return Math.floor(Date.UTC(hk.getUTCFullYear(), hk.getUTCMonth(), hk.getUTCDate()) / MS_PER_DAY)
}

export function parseDateFolderName(name) {
  const text = String(name || '').trim()
  let year
  let month
  let day

  let match = /^(\d{2})(\d{2})(\d{2})$/.exec(text)
  if (match) {
    year = 2000 + Number(match[1])
    month = Number(match[2])
    day = Number(match[3])
  } else if ((match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)) || (match = /^(\d{4})(\d{2})(\d{2})$/.exec(text))) {
    year = Number(match[1])
    month = Number(match[2])
    day = Number(match[3])
  } else {
    return null
  }

  if (year < 2020 || year > 2099 || month < 1 || month > 12 || day < 1 || day > 31) return null
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null
  }
  return { year, month, day, dayIndex: Math.floor(date.getTime() / MS_PER_DAY) }
}

export function isArchivedDateFolder(row, {
  count = 0,
  mentionCount = 0,
  selectedId = '',
  editingId = '',
  editingParentKey = '',
  hasChildren = false,
  todayDayIndex = businessTodayDayIndex(),
  days = ARCHIVE_DATE_FOLDER_DAYS,
} = {}) {
  if (!row || row.builtin || row.isConversation || row.isTechnicalEntry) return false
  if (count > 0 || mentionCount > 0 || hasChildren) return false
  if (row.id === selectedId || row.id === editingId || row.id === editingParentKey) return false
  const parsed = parseDateFolderName(row.name)
  if (!parsed) return false
  return todayDayIndex - parsed.dayIndex > days
}

export function partitionArchivedDateFolders(rows = [], {
  getCount = () => 0,
  getMentionCount = () => 0,
  hasChildren = () => false,
  selectedId = '',
  editingId = '',
  editingParentKey = '',
  todayDayIndex = businessTodayDayIndex(),
  days = ARCHIVE_DATE_FOLDER_DAYS,
} = {}) {
  const activeRows = []
  const archivedRows = []
  for (const row of rows) {
    const archived = isArchivedDateFolder(row, {
      count: getCount(row.id),
      mentionCount: getMentionCount(row.id),
      hasChildren: hasChildren(row.id),
      selectedId,
      editingId,
      editingParentKey,
      todayDayIndex,
      days,
    })
    if (archived) archivedRows.push(row)
    else activeRows.push(row)
  }
  return { activeRows, archivedRows }
}
