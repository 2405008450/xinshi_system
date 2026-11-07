import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {reactive,ref} from 'vue'
import {copySavedValue} from '../src/utils/savedDataMerge.js'
import {paymentConfirmationForm} from '../src/utils/paymentConfirmation.js'
import {taxPriceForm} from '../src/utils/taxPrices.js'
import {newCustomerRate,ratePayload} from '../src/utils/customerTranslationRates.js'

const source=readFileSync(new URL('../src/views/project/translation/CustomerFinance.vue',import.meta.url),'utf8')
const openEditor=source.slice(source.indexOf('async function openEditor(row){'),source.indexOf('async function rebaseEditorAfterLibrary()'))

for(const prices of [[{id:'price',languagePair:'中→英',amount:'0.2',unitSize:'1',taxPrices:{unitPriceExclTax:'0.2'}}],[]]){
  test(`收费窗口可打开同步层返回的响应式订单（${prices.length?'已有单价':'未填单价'}）`,async()=>{
    const data=reactive({version:'v1',item:{id:'order',rootId:'order',orderNo:'TP-261025-003',languagePair:'中→英',prices,children:[],paymentConfirmation:{}},referencePrices:{items:[],version:'r1'}})
    const errors=[]
    const context={structuredClone,copySavedValue,paymentConfirmationForm,taxPriceForm,newCustomerRate,ratePayload,
      canWrite:true,tableEditing:{flush:async()=>true},guardEditor:async()=>true,editorSequence:0,sequence:0,disposed:false,
      timer:null,clearTimeout,controller:null,nextTick:async()=>{},clearFieldSearch:()=>{},referenceDefaults:()=>[],
      getCustomerFinanceProject:async()=>data,orderStatementMonth:()=> '2026-10',editorSignature:()=> 'signature',
      treeVersion:'',libraryVersion:'',original:'',originalPaymentConfirmation:'',
      projectFormTarget:ref(null),documentParent:ref(null),linkedQuotationVisible:ref(false),documentDraft:()=>({}),
      ElMessage:{error:error=>errors.push(error),warning:error=>errors.push(error)},getLocalizedErrorMessage:error=>error.message,
      editor:ref({}),editorVisible:ref(false),editorLoading:ref(false),saving:ref(false),loading:ref(false),financeModule:ref(''),paymentContextId:ref(''),localTarget:ref(null),localPaymentParent:ref(null),originalPrices:ref([]),referencePrices:ref([]),updateLibrary:ref(false),saveError:ref('')}
    vm.createContext(context)
    vm.runInContext(openEditor,context)
    await context.openEditor({id:'order',rootId:'order'})
    assert.deepEqual(errors,[])
    assert.equal(context.editorVisible.value,true)
    assert.equal(context.editorLoading.value,false)
    assert.equal(context.editor.value.prices.length,1)
    context.editor.value.prices[0].amount=9
    if(prices.length)assert.equal(data.item.prices[0].amount,'0.2')
  })
}
