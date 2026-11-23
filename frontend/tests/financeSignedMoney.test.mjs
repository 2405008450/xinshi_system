import test from 'node:test'
import assert from 'node:assert/strict'
import {quotationLineCents,quotationMoney} from '../src/utils/quotation.js'
test('付款负差异不会因正数舍入偏移一分钱',()=>{
  assert.equal(quotationMoney(quotationLineCents({quantity:1,unit_price:'-300.00'},6)),'-300.00')
  assert.equal(quotationMoney(quotationLineCents({quantity:1,unit_price:'-1.005'},6)),'-1.01')
  assert.equal(quotationMoney(quotationLineCents({quantity:1,unit_price:'1.005'},6)),'1.01')
  assert.equal(quotationLineCents({quantity:1,unit_price:'待填写'},6),null)
})
