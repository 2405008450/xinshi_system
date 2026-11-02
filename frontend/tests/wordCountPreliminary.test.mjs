import test from 'node:test'
import assert from 'node:assert/strict'
import {normalizeWordCountMatrix,formatWordCountMatrix} from '../src/utils/wordCountMatrix.js'
import {resolveRateQuantity,calculateOrderPriceTree} from '../src/utils/translationQuantityBasis.js'

test('预统计可保存零值、显示于客户统计之后，并且不能用于计费',()=>{
  const matrix=normalizeWordCountMatrix({preliminary:{foreignWords:999,documents:0}})
  assert.equal(matrix.preliminary.foreign_words,999)
  assert.equal(matrix.preliminary.documents,0)
  assert.match(formatWordCountMatrix(matrix),/预统计/)
  assert.equal(resolveRateQuantity(matrix,'customer_auto').quantity,null)
  const price={currency:'CNY',amount:2,unitSize:1,metric:'company_words'}
  matrix.company.words=10
  assert.deepEqual(calculateOrderPriceTree({wordCountMatrix:matrix,prices:[price]}),{totals:{CNY:'20.00'},incomplete:false})
})
