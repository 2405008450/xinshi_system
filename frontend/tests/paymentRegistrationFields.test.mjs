import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
import {computed,ref,watch,effectScope} from 'vue'
import {paymentConfirmationForm,fixFirstDepositStage,clearPaymentSelection,switchPaymentSelection} from '../src/utils/paymentConfirmation.js'
import {paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature} from '../src/utils/paymentDetails.js'

function editor(t){
  const scope=effectScope();t.after(()=>scope.stop())
  const form=ref({paymentConfirmation:paymentConfirmationForm({isPaid:true,paymentOption:'deposit'}),paymentDraft:[]})
  const ctx={form,computed,watch,paymentConfirmationForm,fixFirstDepositStage,clearPaymentSelection,defineProps(){}}
  vm.createContext(ctx)
  const source=readFileSync(new URL('../src/components/common/PaymentRegistrationFields.vue',import.meta.url),'utf8')
  const script=source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm,'').replace(/^const form=defineModel.*$/gm,'')
  scope.run(()=>vm.runInContext(script,ctx))
  return ctx
}

test('价格窗口定金明细保留首条定金、分期增删、累计实付与尾款核对',t=>{
  const ctx=editor(t),form=ctx.form.value
  assert.equal(form.paymentDraft.length,1);assert.equal(form.paymentDraft[0].stage_type,'deposit')
  form.paymentDraft[0].actual_amount=100;ctx.addPayment()
  assert.equal(form.paymentDraft[1].stage_type,'mid')
  form.paymentDraft[1].stage_type='final';form.paymentDraft[1].actual_amount=200;ctx.syncFromDetails()
  assert.equal(form.paymentConfirmation.fullPaymentSource,'details')
  assert.equal(form.paymentConfirmation.fullPaymentAmount,300)
  ctx.removePayment(1)
  assert.equal(form.paymentDraft.length,1);assert.equal(form.paymentConfirmation.fullPaymentAmount,null)
  ctx.updateConfirmation(clearPaymentSelection(form.paymentConfirmation))
  assert.equal(form.paymentDraft.length,0);assert.equal(form.paymentConfirmation.isPaid,false)
})

test('重复阶段期次校验和定金切换全款清除明细',t=>{
  const ctx=editor(t),form=ctx.form.value
  ctx.addPayment();form.paymentDraft[1].stage_type='deposit'
  let error;ctx.validateStage(1,result=>error=result)
  assert.match(error.message,/期次不能重复/)
  ctx.updateConfirmation({...form.paymentConfirmation,paymentOption:'full',replaceDetails:true,fullPaymentAmount:300})
  assert.equal(form.paymentDraft.length,0)
  assert.equal(form.paymentConfirmation.fullPaymentAmount,300)
})

test('明细往返保留零金额与ID，按UTC+8传输且不修改原始数据',()=>{
  const source=[{id:'payment-1',stageType:'deposit',stageNo:1,actualAmount:'0.00',plannedAmount:null,paymentTime:'2026-11-10T10:30:00Z',paymentMethod:'现金'}]
  const form=paymentDetailsForm(source)
  assert.equal(form[0].actual_amount,0);assert.equal(form[0].payment_time,'2026-11-10 18:30:00')
  const payload=paymentDetailsPayload(form)
  assert.equal(payload[0].payment_time,'2026-11-10T18:30:00+08:00')
  assert.equal(payload[0].planned_amount,null);assert.equal(payload[0].id,'payment-1')
  assert.equal(source[0].actualAmount,'0.00')
  assert.equal(paymentDetailsSignature(form),paymentDetailsSignature(payload))
})

test('各条明细的截图备注相互独立、随明细提交，凭证单独存在也触发切换确认',async t=>{
  const ctx=editor(t),form=ctx.form.value
  form.paymentDraft[0].proofs='定金截图及备注';ctx.addPayment()
  assert.equal(form.paymentDraft[1].proofs,'')
  form.paymentDraft[1].proofs='中期截图及备注'
  assert.equal(form.paymentDraft[0].proofs,'定金截图及备注')
  const payload=paymentDetailsPayload(form.paymentDraft)
  assert.deepEqual(Array.from(payload,item=>item.proofs),['定金截图及备注','中期截图及备注'])
  let prompted=false
  await switchPaymentSelection(form.paymentConfirmation,'full',{payments:payload,confirm:async()=>{prompted=true}})
  assert.equal(prompted,true)
})
