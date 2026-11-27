import test from 'node:test'
import assert from 'node:assert/strict'
import {financeDraft,interpretationFinancePayload,interpretationFinanceTotals} from '../src/utils/interpretationCustomerFinance.js'

test('旧定金资料带出共用付款表单，保存保留币种、日期及凭证',()=>{
  const draft=financeDraft({settlement:{payment_status:'deposit',payments:[{amount:'30',currency:'USD',received_on:'2026-11-26',note:'旧凭证',stage_type:'deposit'}]}})
  assert.equal(draft.paymentConfirmation.paymentOption,'deposit')
  assert.equal(draft.paymentDraft[0].currency,'USD')
  assert.equal(draft.paymentDraft[0].actual_amount,30)
  const payload=interpretationFinancePayload(draft)
  assert.equal(payload.payment_registration.payments[0].payment_time,'2026-11-26T00:00:00+08:00')
  assert.equal(payload.payment_registration.payments[0].proofs,'旧凭证')
  assert.ok(!('paymentDraft' in payload)&&!('paymentConfirmation' in payload))
})
test('已付定金但未补明细时初始化一笔，新增和重开表单不会丢失状态',()=>{
  const draft=financeDraft({settlement:{payment_status:'deposit',payments:[]}})
  assert.equal(draft.paymentDraft.length,1)
  const reopened=financeDraft(interpretationFinancePayload(draft))
  assert.equal(reopened.paymentDraft.length,1)
  assert.equal(reopened.paymentConfirmation.paymentOption,'deposit')
})
test('总价与说明的折扣、手动金额及付款核对按同一计费口径',()=>{
  const draft=financeDraft({rates:[{direction:'中英',amount:100,quantity:2,currency:'CNY',unit:'天',tax_prices:{unit_price_excl_tax:100,unit_price_incl_tax:106}}],settlement:{tax_basis:'incl_tax'},settlement_adjustments:[{currency:'CNY',incl_discount:90,excl_amount:0}]})
  assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'190.80'})
  assert.deepEqual(interpretationFinanceTotals(draft,'excl_tax'),{CNY:'0.00'})
  draft.settlement_adjustments[0].incl_amount=180
  assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'180.00'})
})
test('旧版总价调整和折扣合并展示后保留原最终金额',()=>{
  const draft=financeDraft({rates:[{direction:'中英',amount:100,quantity:2,currency:'CNY',tax_prices:{unit_price_incl_tax:106}}],adjusted_totals:[{amount:180,currency:'CNY',tax_prices:{total_incl_tax:180}}],settlement:{tax_basis:'incl_tax'},settlement_adjustments:[{currency:'CNY',incl_discount:90}]})
  assert.equal(draft.adjusted_totals.length,0)
  assert.equal(draft.settlement_adjustments[0].incl_amount,162)
  assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'162.00'})
})
