import test from 'node:test'
import assert from 'node:assert/strict'
import {quotationLineCents,quotationMoney} from '../src/utils/quotation.js'
test('fractional quote quantities, rounding and zero',()=>{
  assert.equal(quotationMoney(quotationLineCents({quantity:123.5,unit_price:.25})),'30.88')
  assert.equal(quotationMoney(quotationLineCents({quantity:0,unit_price:2})),'0.00')
  assert.equal(quotationLineCents({quantity:null,unit_price:2}),null)
})
