import test from 'node:test'
import assert from 'node:assert/strict'
import { auditChanges, cleanReferralColumns, displayReferralValue, dateText, referralColumns } from '../src/utils/referralDevelopment.js'

test('字段配置保留全部取消并过滤历史字段，非法结构使用调用方默认值', () => {
  assert.deepEqual(cleanReferralColumns([]), [])
  assert.deepEqual(cleanReferralColumns(['amount', 'deleted', 'amount', 'full_name']), ['amount', 'full_name'])
  assert.throws(() => cleanReferralColumns({ amount: true }))
  assert.equal(new Set(referralColumns.map(c => c.key)).size, referralColumns.length)
})

test('零金额、空日期与中文日期时间显示', () => {
  assert.equal(displayReferralValue({ amount: '0.00' }, 'amount'), '0.00')
  assert.equal(displayReferralValue({ amount: '6.25' }, 'amount'), '6.25')
  assert.equal(dateText('2026-08-26'), '2026年08月26日')
  assert.equal(displayReferralValue({ payment_date: null }, 'payment_date'), '-')
  assert.equal(displayReferralValue({ updated_at: '2026-08-26T23:30:00+08:00' }, 'updated_at').includes('23:30'), true)
})

test('付款撤销历史区分原值、空日期和金额变化', () => {
  const changes = auditChanges({ before: { payment_status: 'paid', payment_date: '2026-08-27', amount: '6.00', revision: 2 }, after: { payment_status: 'unpaid', payment_date: null, amount: '0.00', revision: 3 } })
  assert.equal(changes.find(c => c.key === 'payment_status').before, '已支付')
  assert.equal(changes.find(c => c.key === 'payment_date').after, '-')
  assert.equal(changes.find(c => c.key === 'amount').after, '0.00')
  assert.equal(changes.length, 3)
})
