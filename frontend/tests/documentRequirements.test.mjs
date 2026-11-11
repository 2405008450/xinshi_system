import test from 'node:test'
import assert from 'node:assert/strict'
import {documentNotesForm,invoiceRequirement} from '../src/utils/documentRequirements.js'

test('发票需求跟随有效计费口径，单边金额自动判断，未填金额待判断',()=>{
  const order={pricingMode:'fixed',adjustedTotal:100,adjustedTotalInclTax:106,billingTaxMode:'excl_tax'}
  assert.equal(invoiceRequirement(order),false)
  order.billingTaxMode='incl_tax';assert.equal(invoiceRequirement(order),true)
  assert.equal(invoiceRequirement({pricingMode:'fixed',adjustedTotalInclTax:0}),true)
  assert.equal(invoiceRequirement({pricingMode:'fixed'}),null)
})

test('三类说明独立，混合税口径的父订单含税部分需发票',()=>{
  const notes=documentNotesForm({quotation:'报价说明',invoice:'开票说明'})
  assert.deepEqual(notes,{quotation:'报价说明',statement:'',invoice:'开票说明'})
  assert.equal(invoiceRequirement({priceAggregate:true,children:[{pricingMode:'fixed',adjustedTotal:100},{pricingMode:'fixed',adjustedTotalInclTax:106}]}),true)
})
