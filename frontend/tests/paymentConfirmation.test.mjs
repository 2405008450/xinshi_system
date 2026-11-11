import test from 'node:test'
import assert from 'node:assert/strict'
import {paymentConfirmationForm,paymentConfirmationPayload,paymentConfirmationLabel,paymentOptions,preferredPaymentTotalKey,fixFirstDepositStage,clearPaymentSelection} from '../src/utils/paymentConfirmation.js'

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

test('默认优先调整后总价，保留人工选择，并限制同币种',()=>{
  const totals=[{key:'excl:CNY',currency:'CNY',amount:'360'},{key:'adjusted:CNY',currency:'CNY',amount:'350'},{key:'incl:CNY',currency:'CNY',amount:'381.6'},{key:'adjusted:USD',currency:'USD',amount:'50'}]
  assert.equal(preferredPaymentTotalKey(totals,'CNY',null),'adjusted:CNY')
  assert.equal(preferredPaymentTotalKey(totals,'CNY','excl:CNY'),'excl:CNY')
  assert.equal(preferredPaymentTotalKey(totals,'USD','excl:CNY'),'adjusted:USD')
  assert.equal(preferredPaymentTotalKey(totals.filter(item=>!item.key.startsWith('adjusted:')),'CNY',null),'incl:CNY')
  assert.equal(preferredPaymentTotalKey(totals,'EUR',null),null)
})

test('已付定金的首条阶段固定为定金，后续阶段和金额保持不变',()=>{
  const rows=[{stage_type:'mid',stage_no:1,planned_amount:200,actual_amount:100,payment_method:'广州公司公账'},{stage_type:'deposit',stage_no:1,actual_amount:10},{stage_type:'final',stage_no:1,actual_amount:90}]
  const later=structuredClone(rows.slice(1))
  fixFirstDepositStage({isPaid:true,paymentOption:'deposit'},rows)
  assert.equal(rows[0].stage_type,'deposit');assert.equal(rows[0].stage_no,1)
  assert.equal(rows[0].planned_amount,200);assert.equal(rows[0].actual_amount,100)
  assert.equal(rows[0].payment_method,'广州公司公账');assert.deepEqual(rows.slice(1),later)
  fixFirstDepositStage({isPaid:true,paymentOption:'deposit'},rows)
  assert.equal(rows[0].stage_no,1)
})

test('未选择定金或已选择全款时，不改已有付款阶段',()=>{
  for(const confirmation of [{isPaid:false,paymentOption:null},{isPaid:true,paymentOption:'full'}]){
    const rows=[{stage_type:'mid',stage_no:1}]
    fixFirstDepositStage(confirmation,rows)
    assert.equal(rows[0].stage_type,'mid')
  }
})

test('清除付款选择清空当前详情，并向服务器提交清除标记',()=>{
  const original={isPaid:true,paymentOption:'deposit',paymentAccount:'广州公司公账',proofs:'原凭证',fullPaymentAmount:100,fullPaymentTotalKey:'excl:CNY'}
  const cleared=clearPaymentSelection(original)
  assert.equal(cleared.isPaid,false);assert.equal(cleared.paymentOption,null)
  assert.equal(cleared.paymentAccount,'');assert.equal(cleared.proofs,'')
  assert.equal(cleared.fullPaymentAmount,null);assert.equal(cleared.fullPaymentTotalKey,null)
  assert.equal(paymentConfirmationPayload(cleared).clear_details,true)
  assert.equal(original.proofs,'原凭证')
})

test('付款状态切换可取消；确认后清空另一侧，零金额也需确认',async()=>{
  const {switchPaymentSelection}=await import('../src/utils/paymentConfirmation.js')
  const original={isPaid:true,paymentOption:'full',fullPaymentAmount:0,proofs:'原凭证'}
  assert.equal(await switchPaymentSelection(original,'deposit',{confirm:async()=>{throw Error('取消')}}),null)
  assert.equal(original.proofs,'原凭证')
  let prompt=''
  const next=await switchPaymentSelection(original,'deposit',{confirm:async text=>{prompt=text}})
  assert.match(prompt,/已付全款.*付款数据/);assert.equal(next.fullPaymentAmount,null)
  assert.equal(next.proofs,'');assert.equal(next.replaceDetails,true)
})

test('清除选择后再选时仍检查遗留明细；空数据无需确认',async()=>{
  const {switchPaymentSelection}=await import('../src/utils/paymentConfirmation.js')
  let count=0
  const confirm=async()=>{count++}
  await switchPaymentSelection({isPaid:false},'full',{payments:[{stage_type:'deposit',actual_amount:0}],confirm})
  assert.equal(count,1)
  const next=await switchPaymentSelection(clearPaymentSelection({}), 'deposit',{confirm})
  assert.equal(count,1);assert.equal(next.replaceDetails,true);assert.equal(next.paymentOption,'deposit')
})
