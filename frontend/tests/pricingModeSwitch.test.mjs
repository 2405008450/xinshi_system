import test from 'node:test'
import assert from 'node:assert/strict'
import {requestPricingModeSwitch,hasPricingModeData} from '../src/utils/pricingModeSwitch.js'
const createRate=languagePair=>({languagePair,taxPrices:{},amount:undefined})
test('取消切换完整保留原模式、单价、金额和公共信息',async()=>{
  const order={pricingMode:'metric',prices:[{amount:.2}],adjustedTotal:300,explanation:'保留'}
  const before=JSON.stringify(order)
  assert.equal(await requestPricingModeSwitch(order,'fixed',{createRate,confirm:async message=>{assert.match(message,/填写了固定收费.*清除工作量/);throw new Error('cancel')}}),false)
  assert.equal(JSON.stringify(order),before)
})
test('确认切换只清除另一种计价数据，不清字数、说明和付款',async()=>{
  const order={pricingMode:'metric',prices:[{amount:0,referenceId:'ref'}],adjustedTotal:0,adjustedTotalInclTax:20,billingTaxMode:'incl_tax',wordCountMatrix:{customer:{words:2000}},explanation:'内部',customerExplanation:'客户',paymentConfirmation:{isPaid:true}}
  assert.equal(hasPricingModeData(order),true)
  assert.equal(await requestPricingModeSwitch(order,'fixed',{createRate,confirm:async()=>{}}),true)
  assert.deepEqual(order.prices,[])
  assert.equal(order.adjustedTotal,undefined)
  assert.equal(order.adjustedTotalInclTax,undefined)
  assert.equal(order.billingTaxMode,null)
  assert.equal(order.wordCountMatrix.customer.words,2000)
  assert.equal(order.explanation,'内部')
  assert.equal(order.paymentConfirmation.isPaid,true)
})
test('固定收费改工作量会清空固定金额，建立空单价',async()=>{
  const order={pricingMode:'fixed',adjustedTotalInclTax:200,languagePair:'中→英'}
  await requestPricingModeSwitch(order,'metric',{createRate,confirm:async message=>assert.match(message,/填写了工作量.*清除固定收费/)})
  assert.equal(order.pricingMode,'metric')
  assert.equal(order.adjustedTotalInclTax,undefined)
  assert.equal(order.prices[0].languagePair,'中→英')
  assert.equal(order.prices[0].amount,undefined)
})
test('只有默认选项不弹确认；主表确认时不提前修改草稿',async()=>{
  let prompts=0
  const empty={pricingMode:'metric',prices:[createRate('中→英')]}
  await requestPricingModeSwitch(empty,'fixed',{createRate,confirm:async()=>prompts++})
  assert.equal(prompts,0)
  const draft={pricingMode:'fixed',adjustedTotal:0}
  await requestPricingModeSwitch(draft,'metric',{apply:false,confirm:async()=>prompts++})
  assert.equal(prompts,1)
  assert.equal(draft.pricingMode,'fixed')
  assert.equal(draft.adjustedTotal,0)
})
