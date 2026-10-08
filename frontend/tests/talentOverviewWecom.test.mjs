import assert from 'node:assert/strict'
import test from 'node:test'
import { formatOverviewDate, formatOverviewCount, formatOverviewOperationTime, formatOverviewChange } from '../src/utils/talentOverviewWecom.js'

test('群人数区分未登记与零，日期按中文格式且操作时间为香港时区', () => {
  assert.equal(formatOverviewCount(null), '-')
  assert.equal(formatOverviewCount(0), '0')
  assert.equal(formatOverviewDate('2026-10-08'), '2026年10月8日')
  assert.match(formatOverviewOperationTime('2026-10-08T02:03:04Z'), /10:03:04/)
})

test('历史变更保持多行计划、真假状态和空值可辨认', () => {
  const changes = formatOverviewChange({ peopleCount: 0, isBuilt: false, plan: '第一行\n第二行', builtDate: null })
  assert.match(changes, /人数：0/)
  assert.match(changes, /是否已建：否/)
  assert.match(changes, /第一行\n第二行/)
  assert.match(changes, /建群日期：-/)
})
