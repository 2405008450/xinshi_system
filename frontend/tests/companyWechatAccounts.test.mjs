import assert from 'node:assert/strict'
import test from 'node:test'
import { companyWechatAccounts, deletedWechatMarkers, normalizeWechatAccounts, formatWechatAccounts, sameWechatAccounts } from '../src/utils/companyWechatAccounts.js'
import { continueDevelopmentValues, developmentColumns, progressText } from '../src/utils/resourceDevelopment.js'

test('预设账号、删除标记、去重及历史原文兼容', () => {
  assert.equal(companyWechatAccounts.length, 12)
  assert.deepEqual(deletedWechatMarkers, ['已删微信', '已删企微'])
  assert.deepEqual(normalizeWechatAccounts(undefined, '旧名称、保留原文'), ['旧名称、保留原文'])
  assert.deepEqual(normalizeWechatAccounts([' HR1 ', 'HR1', '其他']), ['HR1', '其他'])
  assert.equal(formatWechatAccounts(['HR1', 'HR2企微', '已删微信']), 'HR1、HR2企微、已删微信')
  assert.equal(sameWechatAccounts(['HR1', 'HR2'], ['HR2', 'HR1']), true)
  assert.equal(sameWechatAccounts(['HR1'], ['HR1', '已删微信']), false)
})

test('批次多选独立复制、字段更名和同步来源提示', () => {
  const form = { friend_accounts: ['HR1'] }, retained = continueDevelopmentValues(form)
  form.friend_accounts.push('HR2')
  assert.deepEqual(retained.friend_accounts, ['HR1'])
  assert.equal(developmentColumns.find(c => c.key === 'account_name').label, '交换账号')
  assert.equal(developmentColumns.find(c => c.key === 'wechat_status').label, '添加微信')
  assert.ok(developmentColumns.some(c => c.key === 'friend_accounts_text'))
  assert.match(progressText({ progress: { wechat: { status: '（对方）已删', action_date: '2026-10-08', operator_name: '测试', synchronized: true } } }, 'wechat'), /联系状态同步/)
})
