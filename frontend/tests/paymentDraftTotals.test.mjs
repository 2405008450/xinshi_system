import test from 'node:test'
import assert from 'node:assert/strict'
import {paymentDraftTotals} from '../src/utils/paymentDraftTotals.js'
import {requestPricingModeSwitch} from '../src/utils/pricingModeSwitch.js'

test('切换清空计价数据后，付款核对不保留旧总价',async()=>{
  const order={pricingMode:'fixed',currency:'CNY',adjustedTotal:330,billingTotals:{CNY:'330'},paymentConfirmation:{fullPaymentAmount:330}}
  const calculated={excl:{totals:{}},incl:{totals:{}}}
  assert.equal(paymentDraftTotals(order,calculated)[0].amount,'330.00')
  await requestPricingModeSwitch(order,'metric',{confirm:async()=>{},createRate:()=>({taxPrices:{}})})
  assert.deepEqual(paymentDraftTotals(order,calculated),[])
  assert.equal(order.paymentConfirmation.fullPaymentAmount,330)
})

test('付款核对实时采用当前调整额、含税口径，零金额保留',()=>{
  const order={pricingMode:'metric',currency:'CNY',prices:[{taxPrices:{unitPriceExclTax:.1,unitPriceInclTax:.2}}],adjustedTotalInclTax:0,billingTaxMode:'incl_tax'}
  const items=paymentDraftTotals(order,{excl:{totals:{CNY:'100'}},incl:{totals:{CNY:'200'}}})
  assert.equal(items.find(item=>item.key==='billing:CNY').amount,'0.00')
  assert.equal(items.find(item=>item.key==='excl:CNY').amount,'100.00')
})

test('固定收费单边自动采用；双边沿用计费口径并返回含税标记',()=>{
  const calculated={excl:{totals:{}},incl:{totals:{}}}
  for(const [order,mode,amount] of [
    [{pricingMode:'fixed',adjustedTotal:200},'excl_tax','200.00'],
    [{pricingMode:'fixed',adjustedTotalInclTax:210},'incl_tax','210.00'],
    [{pricingMode:'fixed',adjustedTotal:200,adjustedTotalInclTax:210,billingTaxMode:'incl_tax'},'incl_tax','210.00'],
    [{pricingMode:'fixed',adjustedTotal:200,adjustedTotalInclTax:210,billingTaxMode:'excl_tax'},'excl_tax','200.00'],
  ]){
    const item=paymentDraftTotals(order,calculated).find(item=>item.key==='billing:CNY')
    assert.equal(item.taxMode,mode);assert.equal(item.amount,amount)
  }
})
