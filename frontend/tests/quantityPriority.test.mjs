import test from 'node:test'
import assert from 'node:assert/strict'
import {resolveRateQuantity,rateQuantityOptions,calculateOrderPriceTree} from '../src/utils/translationQuantityBasis.js'
import {normalizeWordCountMatrix} from '../src/utils/wordCountMatrix.js'
test('客户优先、零值有效，缺客户时取我司单位，可手动选我司',()=>{
  const matrix={customer:{pages:0},company:{hours:1.5}}
  assert.equal(resolveRateQuantity(matrix,'customer_auto').metric,'pages')
  assert.equal(resolveRateQuantity(matrix,'customer_auto').quantity,0)
  assert.equal(resolveRateQuantity(matrix,'company_hours').quantity,1.5)
  assert.deepEqual(resolveRateQuantity({company:{hours:1.5}},'customer_auto'),{quantity:1.5,metric:'hours',dimension:'company'})
  assert.match(resolveRateQuantity({},'customer_auto').error,/均未填写/)
  assert.equal(normalizeWordCountMatrix({company:{minutes:2.5}}).company.minutes,2.5)
  assert.ok(rateQuantityOptions(matrix).some(row=>row.value==='company_hours'))
})
test('按所取时长单位计算总价，不把小时误当字数',()=>{
  const result=calculateOrderPriceTree({wordCountMatrix:{company:{hours:1.5}},prices:[{metric:'customer_auto',amount:100,currency:'CNY',unitSize:1}]})
  assert.deepEqual(result.totals,{CNY:'150.00'})
})
