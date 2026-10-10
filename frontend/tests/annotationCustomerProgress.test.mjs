import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import test from 'node:test'
import { appendProgressDraft, progressChatDraft } from '../src/utils/annotationCustomerProgress.js'
import { businessDateTimeInputValue, formatBusinessDateTimeMinute } from '../src/utils/dateTime.js'
import { defaultProgressSearchRange } from '../src/utils/annotationProgressSearch.js'

test('沟通草稿按实际时刻合并，保留发言人和来源，不自动保存', () => {
  const draft = progressChatDraft([
    { content: ' 等待报价确认 ', senderName: '客户经理', createdAt: '2026-10-09T09:30:00Z' },
    { content: '报价已发', senderName: '项目经理', createdAt: '2026-10-09T17:00:00+08:00' },
    { content: '  ', senderName: '空消息' },
  ])
  assert.equal(draft.changeNote, '【项目经理】\n报价已发\n\n【客户经理】\n等待报价确认')
  assert.equal(draft.effectiveOn, '2026-10-09 17:30:00')
  assert.deepEqual(draft.source, { messageCount: 2, senderSummary: '项目经理、客户经理' })
  assert.throws(() => progressChatDraft([]), /请先选择/)
})

test('跨线草稿只追加，长度超限时保留两边原文', () => {
  assert.equal(appendProgressDraft('已有草稿', '带入消息'), '已有草稿\n\n带入消息')
  assert.equal(appendProgressDraft('', ' 带入消息 '), '带入消息')
  const existing = '甲'.repeat(9999), incoming = '乙'
  assert.throws(() => appendProgressDraft(existing, incoming), /超过 10000/)
  assert.equal(existing.length, 9999)
})

test('客户进度表单及日期检索明确使用香港时间', () => {
  assert.equal(businessDateTimeInputValue('2026-10-09T16:30:00Z'), '2026-10-10 00:30:00')
  assert.equal(formatBusinessDateTimeMinute('2026-10-09T16:30:00Z'), '2026年10月10日 00:30')
  assert.equal(businessDateTimeInputValue('2026-10-10 00:30:00'), '2026-10-10 00:30:00')
  assert.equal(businessDateTimeInputValue(null), '')
  assert.deepEqual(defaultProgressSearchRange(new Date('2026-10-09T16:30:00Z')), ['2026-07-10', '2026-10-10'])
})

test('香港、UTC和美国西海岸的进度输入与显示一致', () => {
  const script = `import { businessDateTimeInputValue, formatBusinessDateTimeMinute } from './src/utils/dateTime.js'; process.stdout.write(JSON.stringify([businessDateTimeInputValue('2026-10-09T09:18:43Z'),formatBusinessDateTimeMinute('2026-10-09T17:18:43+08:00')]))`
  for (const TZ of ['Asia/Hong_Kong', 'UTC', 'America/Los_Angeles']) {
    const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], { cwd: new URL('..', import.meta.url), env: { ...process.env, TZ }, encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
    assert.deepEqual(JSON.parse(result.stdout), ['2026-10-09 17:18:43', '2026年10月09日 17:18'])
  }
})
