import test from 'node:test'
import assert from 'node:assert/strict'
import {paymentConfirmationForm,paymentConfirmationPayload,paymentConfirmationLabel,paymentOptions} from '../src/utils/paymentConfirmation.js'

test('付款只提供定金和全款；全款金额及原因在两个窗口间完整传输',()=>{
  assert.deepEqual(paymentOptions.map(item=>item.value),['deposit','full'])
  const source={revision:3,is_paid:true,payment_option:'full',full_payment_amount:'90.00',full_payment_currency:'CNY',full_payment_total_key:'excl:CNY',full_match_status:'mismatch',full_reference_label:'不含税总价',full_reference_amount:'100.00',mismatch_reason:'客户确认优惠10元',proofs:'原凭证'}
  const form=paymentConfirmationForm(source)
  assert.equal(form.fullPaymentAmount,90)
  assert.equal(form.fullMatchStatus,'mismatch')
  assert.equal(paymentConfirmationPayload(form).mismatch_reason,source.mismatch_reason)
  assert.equal(paymentConfirmationPayload(form).proofs,'原凭证')
  assert.match(paymentConfirmationLabel(form),/不匹配.*客户确认优惠10元/)
})

test('历史全款不伪造匹配；历史分次付款仍可显示',()=>{
  assert.equal(paymentConfirmationForm({is_paid:true,payment_option:'full'}).fullMatchStatus,'unverified')
  assert.match(paymentConfirmationLabel({is_paid:true,payment_option:'once'}),/分次付款/)
})
