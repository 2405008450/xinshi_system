import {paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature} from '../src/utils/paymentDetails.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {computed,reactive,ref} from 'vue'
import {copySavedValue} from '../src/utils/savedDataMerge.js'
import {paymentConfirmationForm} from '../src/utils/paymentConfirmation.js'
import {taxPriceForm} from '../src/utils/taxPrices.js'
import {newCustomerRate,ratePayload} from '../src/utils/customerTranslationRates.js'
import {requestPricingModeSwitch} from '../src/utils/pricingModeSwitch.js'

const source=readFileSync(new URL('../src/views/project/translation/CustomerFinance.vue',import.meta.url),'utf8')
const section=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end))
const openEditor=section('async function openEditor(row){','async function rebaseEditorAfterLibrary(')

for(const prices of [[{id:'price',languagePair:'中→英',amount:'0.2',unitSize:'1',taxPrices:{unitPriceExclTax:'0.2'}}],[]]){
  test(`收费窗口可打开同步层返回的响应式订单（${prices.length?'已有单价':'未填单价'}）`,async()=>{
    const data=reactive({version:'v1',item:{id:'order',rootId:'order',orderNo:'TP-261025-003',languagePair:'中→英',prices,children:[],paymentConfirmation:{}},referencePrices:{items:[],version:'r1'}})
    const errors=[]
    const context={paymentDetailsForm,paymentDetailsSignature,originalPaymentDetails:ref('[]'),structuredClone,copySavedValue,paymentConfirmationForm,taxPriceForm,newCustomerRate,ratePayload,
      canWrite:true,tableEditing:{flush:async()=>true},guardEditor:async()=>true,editorSequence:0,sequence:0,disposed:false,
      timer:null,clearTimeout,controller:null,nextTick:async()=>{},clearFieldSearch:()=>{},referenceDefaults:()=>{throw new Error('不得自动采用客户参考价')},
      getCustomerFinanceProject:async()=>data,orderStatementMonth:()=> '2026-10',editorSignature:()=> 'signature',
      treeVersion:'',libraryVersion:'',original:ref(''),pricingModeOnlySignature:ref(null),originalPaymentConfirmation:ref(''),
      projectFormTarget:ref(null),documentParent:ref(null),linkedQuotationVisible:ref(false),documentDraft:()=>({}),
      ElMessage:{error:error=>errors.push(error),warning:error=>errors.push(error)},getLocalizedErrorMessage:error=>error.message,
      editor:ref({}),editorVisible:ref(false),editorLoading:ref(false),saving:ref(false),loading:ref(false),financeModule:ref(''),paymentContextId:ref(''),localTarget:ref(null),localPaymentParent:ref(null),originalPrices:ref([]),referencePrices:ref([]),updateLibrary:ref(false),saveError:ref('')}
    vm.createContext(context)
    vm.runInContext(openEditor,context)
    await context.openEditor({id:'order',rootId:'order'})
    assert.deepEqual(errors,[])
    assert.equal(context.editorVisible.value,true)
    assert.equal(context.editorLoading.value,false)
    assert.equal(context.editor.value.prices.length,prices.length)
    if(prices.length)context.editor.value.prices[0].amount=9
    if(prices.length)assert.equal(data.item.prices[0].amount,'0.2')
  })
}

test('放弃计价方式切换后，重开恢复已保存的计价方式、单价、金额及付款信息',async()=>{
  const item=reactive({id:'order',rootId:'order',orderNo:'TP-261025-003',pricingMode:'metric',currency:'CNY',
    languagePair:'中→英',prices:[{id:'rate',languagePair:'中→英',amount:'0.25',unitSize:1,taxPrices:{unitPriceExclTax:'0.25'}}],
    adjustedTotal:'125',explanation:'原内部说明',children:[],paymentConfirmation:{isPaid:true,paymentOption:'full',fullPaymentAmount:125}})
  const confirmationButtons=[]
  const errors=[]
  const context={paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature,originalPaymentDetails:ref('[]'),
    copySavedValue,paymentConfirmationForm,taxPriceForm,newCustomerRate,ratePayload,requestPricingModeSwitch,
    canWrite:true,tableEditing:{flush:async()=>true},editorSequence:0,sequence:0,disposed:false,
    timer:null,clearTimeout,controller:null,nextTick:async()=>{},clearFieldSearch:()=>{},
    getCustomerFinanceProject:async()=>({item,version:'v1'}),orderStatementMonth:()=> '2026-10',
    treeVersion:'',libraryVersion:'',original:ref(''),pricingModeOnlySignature:ref(null),pricingModeBeforeSwitch:null,
    originalPaymentConfirmation:ref(''),formRef:ref(),pricingModeSwitching:ref(false),
    projectFormTarget:ref(null),documentParent:ref(null),linkedQuotationVisible:ref(false),documentDraft:()=>({}),
    ElMessage:{error:error=>errors.push(error)},getLocalizedErrorMessage:error=>error.message,
    ElMessageBox:{confirm:async(_text,_title,options)=>confirmationButtons.push(options.confirmButtonText)},
    editor:ref({}),editorVisible:ref(false),editorLoading:ref(false),saving:ref(false),loading:ref(false),
    financeModule:ref(''),paymentContextId:ref(''),localTarget:ref(null),localPaymentParent:ref(null),
    originalPrices:ref([]),referencePrices:ref([]),updateLibrary:ref(false),saveError:ref('')}
  vm.createContext(context)
  vm.runInContext([
    openEditor,
    section('function paymentConfirmationInput(', 'function stopUsingReference('),
    section('async function closeEditor(done){','async function clearAllFinance('),
    section('function pricingModeSnapshot(', 'async function updateProjectFormFinance('),
  ].join('\n'),context)
  context.editorDirty=computed(()=>context.editorVisible.value&&context.editorSignature()!==context.original.value)
  const row={id:'order',rootId:'order'}
  await context.openEditor(row)
  await context.changePricingMode('fixed')
  assert.equal(context.editor.value.pricingMode,'fixed')
  assert.equal(context.editor.value.prices.length,0)
  assert.equal(context.editorDirty.value,true)
  await context.closeEditor()
  assert.equal(context.editorVisible.value,false)
  assert.equal(confirmationButtons.at(-1),'放弃修改')
  assert.equal(context.pricingModeOnlySignature.value,null)

  await context.openEditor(row)
  assert.deepEqual(errors,[])
  assert.equal(context.editor.value.pricingMode,'metric')
  assert.equal(context.editor.value.prices[0].amount,0.25)
  assert.equal(context.editor.value.adjustedTotal,125)
  assert.equal(context.editor.value.explanation,'原内部说明')
  assert.equal(context.editor.value.paymentConfirmation.fullPaymentAmount,125)
  assert.equal(context.editorDirty.value,false)
})
