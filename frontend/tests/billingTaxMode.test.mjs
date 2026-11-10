import test from 'node:test'
import assert from 'node:assert/strict'
import {billingTaxChoices,effectiveBillingTaxMode,hasFixedFeeAmount} from '../src/utils/billingTaxMode.js'
test('只有一种税口径时自动采用，包括零值',()=>{
  const order={billingTaxMode:'excl_tax',prices:[{taxPrices:{unitPriceInclTax:0}}]}
  assert.deepEqual(billingTaxChoices(order),['incl_tax'])
  assert.equal(effectiveBillingTaxMode(order),'incl_tax')
  assert.equal(effectiveBillingTaxMode({adjustedTotal:0}),'excl_tax')
  assert.equal(effectiveBillingTaxMode({...order,totalsExclTax:{CNY:'200'}}),'incl_tax')
})
test('都有金额时尊重人工选择和已保存的默认口径',()=>{
  const order={prices:[{taxPrices:{unitPriceInclTax:.21,unitPriceExclTax:.2}}]}
  assert.equal(effectiveBillingTaxMode({...order,billingTaxMode:'incl_tax'}),'incl_tax')
  assert.equal(effectiveBillingTaxMode({...order,effectiveBillingTaxMode:'incl_tax'}),'incl_tax')
  assert.equal(effectiveBillingTaxMode({prices:[]} ),null)
})
test('固定收费只看固定金额，不受切换前的单价和旧汇总干扰',()=>{
  const order={pricingMode:'fixed',billingTaxMode:'excl_tax',adjustedTotalInclTax:200,prices:[{taxPrices:{unitPriceExclTax:.12}}],totalsExclTax:{CNY:'360'}}
  assert.deepEqual(billingTaxChoices(order),['incl_tax'])
  assert.equal(effectiveBillingTaxMode(order),'incl_tax')
  assert.equal(hasFixedFeeAmount(order),true)
  assert.equal(hasFixedFeeAmount({adjustedTotalInclTax:0}),true)
  assert.equal(hasFixedFeeAmount({adjustedTotal:null,adjustedTotalInclTax:undefined}),false)
})
