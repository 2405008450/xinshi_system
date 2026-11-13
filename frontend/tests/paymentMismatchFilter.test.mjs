import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
import {ref,reactive,computed} from 'vue'
import {fullPaymentMismatchOption,paymentStatusLabel} from '../src/utils/paymentConfirmation.js'
const source=readFileSync(new URL('../src/components/common/ProjectPaymentDialog.vue',import.meta.url),'utf8')

function harness(response){
  const ctx={paymentFilters:reactive({months:['2020-01'],client:'其他客户',status:fullPaymentMismatchOption.value}),
    projectSort:ref(),activeTab:ref('overview'),managerScope:ref('self'),managerIds:ref([]),projectPage:ref(2),props:{},selectedId:ref(''),
    previousSelectionScope:'',projectTable:ref(null),selectedProjects:ref([]),searchSequence:0,controller:null,projectTimer:null,clearTimeout,AbortController,
    options:ref([{id:'old-unpaid',paymentStatus:'unpaid'}]),projectTotal:ref(1),error:ref(''),searching:ref(false),
    getCustomerFinancePage:async()=>response,getLocalizedErrorMessage:e=>e.message,load:async()=>{}}
  ctx.mismatchView=computed(()=>ctx.activeTab.value==='overview'&&ctx.paymentFilters.status===fullPaymentMismatchOption.value)
  ctx.collectionDefaultView=computed(()=>ctx.activeTab.value==='collection'&&!ctx.paymentFilters.status)
  vm.createContext(ctx)
  vm.runInContext(source.slice(source.indexOf('function collectBillingCurrencies('),source.indexOf('function cacheManagers(')),ctx)
  vm.runInContext(source.slice(source.indexOf('function paymentQuery('),source.indexOf('function queueClientSearch(')),ctx)
  vm.runInContext(source.slice(source.indexOf('async function searchProjects('),source.indexOf('async function onPaymentTabChanged(')),ctx)
  return ctx
}

test('独立核对不发送左侧三条件，保留经理范围与分页；退出恢复原筛选',()=>{
  const ctx=harness({})
  const query=ctx.paymentQuery('订单')
  assert.equal(query.billing_months,undefined);assert.equal(query.client,undefined);assert.equal(query.payment_status,undefined)
  assert.equal(query.payment_amount_mismatch,true);assert.equal(query.only_mine,true)
  assert.equal(query.skip,20);assert.equal(query.keyword,'订单')
  ctx.paymentFilters.status='unpaid'
  const ordinary=ctx.paymentQuery('')
  assert.deepEqual(Array.from(ordinary.billing_months),['2020-01']);assert.equal(ordinary.client,'其他客户');assert.equal(ordinary.payment_status,'unpaid')
})

test('只有已付全款且金额不匹配的记录使用新状态文案',()=>{
  assert.equal(paymentStatusLabel({paymentStatus:'full',paymentAmountMismatch:true}),fullPaymentMismatchOption.label)
  assert.equal(paymentStatusLabel({paymentStatus:'full',paymentAmountMismatch:false}),'已付全款')
  assert.equal(paymentStatusLabel({paymentStatus:'deposit',paymentAmountMismatch:true}),'已付定金')
})

test('旧后端忽略参数或返回未付款项目时清空结果并提示，不能伪装筛选成功',async()=>{
  for(const response of [
    {items:[{id:'unpaid',paymentStatus:'unpaid'}],total:1},
    {paymentAmountMismatchFilterApplied:true,items:[{id:'unpaid',paymentStatus:'unpaid',paymentAmountMismatch:true}],total:1},
  ]){
    const ctx=harness(response);await ctx.searchProjects('')
    assert.equal(ctx.options.value.length,0);assert.equal(ctx.projectTotal.value,0)
    assert.match(ctx.error.value,/后端未正确执行/);assert.equal(ctx.searching.value,false)
  }
})

test('核对列表只展示已付全款母订单，不混入没有独立付款状态的子订单',async()=>{
  const ctx=harness({paymentAmountMismatchFilterApplied:true,items:[{id:'full',paymentStatus:'full',paymentAmountMismatch:true,children:[{id:'child'}]}],total:1})
  await ctx.searchProjects('')
  assert.equal(ctx.options.value[0].id,'full');assert.equal(ctx.options.value[0].children,undefined)
  assert.equal(ctx.projectTotal.value,1);assert.equal(ctx.error.value,'')
})

test('付款查看窗口移除登记选项卡，编辑操作回到统一价格与付款入口',()=>{
  assert.doesNotMatch(source, /label="付款登记"|name="register"|save\(sync/)
  const events=[],ctx={emit:(...args)=>events.push(args)};vm.createContext(ctx)
  vm.runInContext(source.slice(source.indexOf('function openPaymentRow('),source.indexOf('function reloadPayment(')),ctx)
  ctx.openPaymentRow({id:'p1'})
  assert.equal(events[0][0],'edit');assert.equal(events[0][1].id,'p1')
  assert.deepEqual(events[1],['update:modelValue',false])
})
