import {paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature} from '../src/utils/paymentDetails.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {ref} from 'vue'
import {clearFinanceForm,isClearedFinanceForm} from '../src/utils/clearFinanceForm.js'
import {hasFixedFeeAmount} from '../src/utils/billingTaxMode.js'
import {paymentConfirmationForm,paymentConfirmationPayload} from '../src/utils/paymentConfirmation.js'
const source=readFileSync(new URL('../src/views/project/translation/CustomerFinance.vue',import.meta.url),'utf8')
const ruleStart=source.indexOf('validator:(_rule,_value,callback)=>callback(!editor.fixedPricingFrom')
const rule=source.slice(ruleStart+'validator:'.length,source.indexOf(",trigger:'change'",ruleStart))
function validate(order){let error;const ctx={editor:order,isClearedFinanceForm,hasFixedFeeAmount};vm.createContext(ctx);vm.runInContext(`(${rule})`,ctx)(null,null,value=>{error=value});return error}

test('固定收费清空后，打开关联付款但不操作，返回可保存空数据',async()=>{
  const editor=ref(clearFinanceForm({id:'root',rootId:'root',pricingMode:'fixed',adjustedTotal:330,paymentConfirmation:{revision:5,isPaid:false}}))
  assert.equal(editor.value.pricingMode,'fixed');assert.equal(validate(editor.value),undefined)
  const calls=[],errors=[]
  const ctx={paymentDetailsDirty:ref(false),paymentDetailsForm,paymentDetailsSignature,paymentDetailsPayload,originalPaymentDetails:ref('[]'),editor,isClearedFinanceForm,hasFixedFeeAmount,paymentConfirmationForm,paymentConfirmationPayload,
    linkedPaymentVisible:ref(false),saving:ref(false),canWrite:true,formRef:ref({validate:async()=>!validate(editor.value)}),localTarget:ref(null),
    documentPayload:()=>({}),treeVersion:'v1',libraryVersion:'r1',billingTaxChoices:()=>[],effectiveBillingTaxMode:()=>null,paymentConfirmationDirty:ref(true),
    updateLibrary:ref(false),saveError:ref(''),updateProjectFormFinance:async()=>{},applyDocumentDraft:()=>{},syncSavedFinanceRows:()=>{},
    notifyStatementCustomerSync:()=>{},window:{dispatchEvent:()=>{}},CustomEvent:class{},
    saveCustomerFinanceProject:async(id,payload)=>{calls.push(payload);return {item:{paymentConfirmation:{revision:6,isPaid:false}}}},
    editorSignature:()=>'',original:ref(''),pricingModeOnlySignature:ref(null),originalPaymentConfirmation:ref(''),notifyPaymentChanged:()=>{},financePaymentSource:'test',editorVisible:ref(true),
    ElMessage:{warning:value=>errors.push(value),success:()=>{}},emit:()=>{},load:async()=>{},getLocalizedErrorMessage:e=>e.message}
  vm.createContext(ctx)
  vm.runInContext(source.slice(source.indexOf('async function openLinkedPayment()'),source.indexOf('function onPaymentSaved(')),ctx)
  vm.runInContext(source.slice(source.indexOf('async function save(syncToClient=false)'),source.indexOf('watch(()=>[editor.value.pricingMode')),ctx)
  await ctx.openLinkedPayment();ctx.linkedPaymentVisible.value=false
  await ctx.save()
  assert.deepEqual(errors,[]);assert.equal(ctx.saveError.value,'')
  assert.equal(calls.length,1);assert.equal(calls[0].clear_finance,true)
  assert.equal(calls[0].pricing_mode,'fixed');assert.equal(calls[0].prices,null)
  assert.equal(calls[0].adjusted_total,null);assert.equal(calls[0].payment_confirmation.is_paid,false)
})

test('正常固定收费仍须金额；清空后重新填写零金额恢复正常保存路径',()=>{
  assert.match(validate({pricingMode:'fixed'})?.message||'',/请填写/)
  const order=clearFinanceForm({pricingMode:'fixed'})
  assert.equal(isClearedFinanceForm(order),true)
  order.adjustedTotal=0
  assert.equal(isClearedFinanceForm(order),false);assert.equal(validate(order),undefined)
})
