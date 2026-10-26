import test from 'node:test'
import assert from 'node:assert/strict'
import { compareProgressByDate } from '../src/utils/annotationProgressComparison.js'

test('三条进度按香港业务日期对齐，不按接口中的字符串偏移分组', () => {
  const result = compareProgressByDate({
    project: [{ id: 'p', effectiveOn: '2026-10-22T17:00:00Z', toStatus: 'trial_preparation' }],
    customer: [{ id: 'c', effectiveOn: '2026-10-23 01:30:00' }],
    annotator: [{ id: 'a', effectiveOn: '2026-10-22T23:59:00+08:00' }],
  })
  assert.deepEqual(result.days.map(row => row.day), ['2026-10-23', '2026-10-22'])
  assert.equal(result.days[0].project[0].id, 'p')
  assert.equal(result.days[0].customer[0].id, 'c')
  assert.deepEqual(result.days[0].annotator, [])
})

test('各线按节点时间和登记时间倒序选出最新记录，保留同一天全部记录且不修改来源', () => {
  const rows = [
    { id: 'old', effectiveOn: '2026-10-23 10:00:00', changedAt: '2026-10-23 12:00:00' },
    { id: 'new', effectiveOn: '2026-10-23T11:00:00+08:00', changedAt: '2026-10-23 12:30:00' },
    { id: 'tie', effectiveOn: '2026-10-23T03:00:00Z', changedAt: '2026-10-23 13:00:00' },
  ]
  const result = compareProgressByDate({ project: rows })
  assert.equal(result.tracks[0].latest.id, 'tie')
  assert.deepEqual(result.days[0].project.map(row => row.id), ['tie', 'new', 'old'])
  assert.equal(rows[0].businessTime, undefined)
  assert.equal(rows[0].id, 'old')
})

test('空进度与缺失时间明确展示，不将未知日期当成最新日期', () => {
  const result = compareProgressByDate({ customer: [{ id: 'unknown' }, { id: 'known', effectiveOn: '2026-10-23 09:00:00' }] })
  assert.equal(result.tracks.length, 3)
  assert.equal(result.tracks[0].latest, null)
  assert.deepEqual(result.days.map(row => row.day), ['2026-10-23', '未标注时间'])
  assert.equal(result.tracks[1].latest.id, 'known')
})
