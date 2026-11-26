import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ARCHIVE_DATE_FOLDER_DAYS,
  businessTodayDayIndex,
  isArchivedDateFolder,
  parseDateFolderName,
  partitionArchivedDateFolders,
} from '../src/utils/chatDateFolderArchive.js'

test('parseDateFolderName 正确解析 YYMMDD / YYYYMMDD / YYYY-MM-DD 并拒绝非法日期和普通分组名', () => {
  assert.deepEqual(parseDateFolderName('261126'), { year: 2026, month: 11, day: 26, dayIndex: Math.floor(Date.UTC(2026, 10, 26) / 86400000) })
  assert.deepEqual(parseDateFolderName('2026-10-01'), { year: 2026, month: 10, day: 1, dayIndex: Math.floor(Date.UTC(2026, 9, 1) / 86400000) })
  assert.deepEqual(parseDateFolderName('20260228'), { year: 2026, month: 2, day: 28, dayIndex: Math.floor(Date.UTC(2026, 1, 28) / 86400000) })
  assert.equal(parseDateFolderName('20260229'), null)
  assert.equal(parseDateFolderName('261345'), null)
  assert.equal(parseDateFolderName('笔译项目管理讨论'), null)
})

test('businessTodayDayIndex 按 UTC+8 换日而非 UTC', () => {
  // UTC 2026-11-25 16:30:00 === HK 2026-11-26 00:30:00
  const hkMidnight = new Date('2026-11-25T16:30:00Z')
  assert.equal(businessTodayDayIndex(hkMidnight), parseDateFolderName('261126').dayIndex)
})

test('超过 30 天且无活跃会话、无未读提及、未选中的老日期文件夹自动归档，活跃或保护项不归档', () => {
  const today = parseDateFolderName('261126').dayIndex
  assert.equal(ARCHIVE_DATE_FOLDER_DAYS, 30)

  const day30 = { id: 'd30', name: '261027' } // 差 30 天：不归档
  const day31Empty = { id: 'd31', name: '261026' } // 差 31 天且空：归档
  const day31Active = { id: 'd31-act', name: '261026' }
  const day31Mention = { id: 'd31-men', name: '261026' }
  const day31Selected = { id: 'd31-sel', name: '261026' }
  const normal = { id: 'norm', name: '重点客户' }

  assert.equal(isArchivedDateFolder(day30, { todayDayIndex: today }), false)
  assert.equal(isArchivedDateFolder(day31Empty, { todayDayIndex: today }), true)
  assert.equal(isArchivedDateFolder(day31Active, { count: 1, todayDayIndex: today }), false)
  assert.equal(isArchivedDateFolder(day31Mention, { mentionCount: 2, todayDayIndex: today }), false)
  assert.equal(isArchivedDateFolder(day31Selected, { selectedId: 'd31-sel', todayDayIndex: today }), false)
  assert.equal(isArchivedDateFolder(normal, { todayDayIndex: today }), false)
})

test('partitionArchivedDateFolders 在数百历史日期下默认仅保留近期与活跃分组', () => {
  const today = parseDateFolderName('261126').dayIndex
  const rows = [
    { id: 'mgmt', name: '笔译项目管理讨论', isConversation: true },
    { id: 'recent-1', name: '261126' },
    { id: 'recent-2', name: '261110' },
    { id: 'old-empty-1', name: '260901' },
    { id: 'old-empty-2', name: '260815' },
    { id: 'old-active', name: '260801' },
  ]
  const counts = new Map([['old-active', 2]])
  const { activeRows, archivedRows } = partitionArchivedDateFolders(rows, {
    getCount: id => counts.get(id) || 0,
    todayDayIndex: today,
  })
  assert.deepEqual(activeRows.map(r => r.id), ['mgmt', 'recent-1', 'recent-2', 'old-active'])
  assert.deepEqual(archivedRows.map(r => r.id), ['old-empty-1', 'old-empty-2'])
})
