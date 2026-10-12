import assert from 'node:assert/strict'
import test from 'node:test'
import { cleanColumns, developmentColumns, followUpText, followUpTime } from '../src/utils/resourceDevelopment.js'

test('旧跟进字段配置合并且不产生重复列', () => {
  assert.deepEqual(cleanColumns(['follow_up', 'latest_follow_up', 'full_name']), ['full_name', 'latest_follow_up'])
  assert.equal(developmentColumns.find(column => column.key === 'latest_follow_up').label, '后续跟进情况')
  assert.equal(developmentColumns.some(column => column.key === 'follow_up'), false)
})

test('历史操作时间按香港时区显示，列表只显示跟进摘要并兼容历史原文', () => {
  assert.equal(followUpTime('2026-10-07T16:01:02Z'), '2026年10月08日 00:01:02')
  assert.equal(followUpTime(null), '-')
  assert.equal(followUpText({ follow_up: '旧文本' }), '旧文本')
  assert.equal(followUpText({}), '')
  assert.equal(followUpText({ latest_follow_up_entry: { content: '回复\n待确认', operator_name: '实际保存人', created_at: '2026-10-08T13:04:05+08:00' } }), '回复 待确认')
  const long = followUpText({ latest_follow_up_entry: { content: '文'.repeat(20000), operator_name: '操作人', created_at: '2026-10-08T13:04:05+08:00' } })
  assert.equal(long, `${'文'.repeat(100)}…`)
})
