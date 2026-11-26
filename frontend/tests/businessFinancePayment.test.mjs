import test from 'node:test'
import assert from 'node:assert/strict'
import {businessPaymentForm,businessPaymentPayload} from '../src/utils/businessFinancePayment.js'

test('标注复用付款表单保留币种、每期凭证、计划金额和香港时间',()=>{
  const value={confirmation:{is_paid:true,payment_option:'deposit'},payments:[{stage_type:'deposit',currency:'USD',planned_amount:'100',actual_amount:'80',proofs:'凭证',payment_time:'2026-11-24T15:00:00+08:00'}]}
  const payload=businessPaymentPayload(businessPaymentForm(value))
  assert.equal(payload.payments[0].currency,'USD')
  assert.equal(payload.payments[0].planned_amount,100)
  assert.equal(payload.payments[0].actual_amount,80)
  assert.equal(payload.payments[0].proofs,'凭证')
  assert.equal(payload.payments[0].payment_time,'2026-11-24T15:00:00+08:00')
})
test('历史全款日期在表单回填后保留',()=>{
  assert.equal(businessPaymentPayload(businessPaymentForm({full_payment_received_on:'2026-11-20'})).full_payment_received_on,'2026-11-20')
})
