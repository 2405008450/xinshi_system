import assert from 'node:assert/strict'
import test from 'node:test'
import { newEntryRow, entryPayload, entryNeedsEnrollment } from '../src/utils/developmentBatchEntry.js'
import { dateText } from '../src/utils/resourceDevelopment.js'

test('新增默认香港当天，周一不回退周五，UTC 午夜前后不受浏览器时区影响', () => {
  assert.equal(newEntryRow({ user_id: 'u' }, {}, new Date('2026-10-26T03:00:00Z')).work_date, '2026-10-26')
  assert.equal(dateText(new Date('2026-10-25T16:01:00Z')), '2026-10-26')
  assert.equal(dateText(new Date('2026-10-25T15:59:59Z')), '2026-10-25')
})
test('复制完整模板但生成独立标识、数组和账号，清空上次关联与错误', () => {
  const first = newEntryRow({ user_id: 'u' }, { full_name: '模板', language_ids: ['l'], friend_accounts: ['a'], whatsapp: 'wa', custom_accounts: [{ name: 'Telegram', value: 'tg' }], follow_up_content: '已联系', _statuses: { wechat: '一次请求' }, link_person_id: 'old', _error: '旧错误' })
  const copy = newEntryRow({ user_id: 'u' }, first)
  assert.notEqual(copy.id, first.id)
  assert.notEqual(copy._actionIds.wechat, first._actionIds.wechat)
  assert.notEqual(copy._followupId, first._followupId)
  copy.language_ids.push('new'); copy.custom_accounts[0].value = 'changed'
  assert.deepEqual(first.language_ids, ['l'])
  assert.equal(first.custom_accounts[0].value, 'tg')
  assert.equal(copy.link_person_id, null)
  assert.equal(copy._error, '')
  assert.equal(copy.full_name, '模板')
})
test('保存只发送业务字段，稳定 UUID 支持响应丢失后重试，私域入库条件正确', () => {
  const row = newEntryRow({ user_id: 'u' }, { full_name: '某资源', _statuses: { wechat: '一次请求' }, follow_up_content: ' 跟进说明 ' })
  assert.equal(entryNeedsEnrollment(row), false)
  const payload = entryPayload(row)
  assert.equal('_statuses' in payload, false)
  assert.equal(payload.actions[0].operator_id, 'u')
  assert.equal(payload.follow_ups[0].content, '跟进说明')
  assert.deepEqual(entryPayload(row), payload)
  row._statuses.wechat = '已添加'
  assert.equal(entryNeedsEnrollment(row), true)
})
