import test from 'node:test'
import assert from 'node:assert/strict'
import {resolveRateQuantity,quantityBasisOptions,calculateOrderPriceTree} from '../src/utils/translationQuantityBasis.js'
test('客户字数自动使用唯一已填栏，包括零和份页，不把多栏相加',()=>{
  assert.equal(resolveRateQuantity({customer:{pages:0}},'customer_auto').quantity,0)
  assert.equal(resolveRateQuantity({customer:{foreignWords:123}},'customer_auto').quantity,123)
  assert.equal(resolveRateQuantity({customer:{words:20,charactersNoSpaces:50}},'customer_auto').quantity,null)
  assert.equal(resolveRateQuantity({customer:{words:20,charactersNoSpaces:50}},'customer_auto:words').quantity,20)
  assert.equal(quantityBasisOptions.length,7)
})
test('我司口径独立读取，不误用客户统计',()=>{
  assert.equal(resolveRateQuantity({company:{words:15},customer:{words:100}},'company_words').quantity,15)
  assert.equal(resolveRateQuantity({company:{foreignWords:12},customer:{foreignWords:99}},'company_foreign_words').quantity,12)
  for(const [metric,count] of [['documents',3],['pages',8]]){
    const matrix={company:{[metric]:count},customer:{[metric]:999}}
    const result=calculateOrderPriceTree({wordCountMatrix:matrix,prices:[{metric:'company_'+metric,amount:2,currency:'CNY',unitSize:1}]})
    assert.equal(result.totals.CNY,(2*count).toFixed(2))
    assert.equal(result.incomplete,false)
  }
})
test('父级草稿计算下级总价，保留独立修改价且不重复计数',()=>{
  const price=amount=>({languagePair:'英语→简中',amount,currency:'CNY',metric:'customer_auto',unitSize:1})
  const node={languagePair:'英语→简中',wordCountMatrix:{customer:{words:999}},prices:[price(.2)],children:[{languagePair:'英语→简中',wordCountMatrix:{customer:{words:100}},prices:[price(.1)]},{languagePair:'英语→简中',wordCountMatrix:{customer:{words:20}},prices:[price(.5)]}]}
  assert.deepEqual(calculateOrderPriceTree(node,[price(.1)]),{totals:{CNY:'30.00'},incomplete:false})
  node.children[0].wordCountMatrix.customer.charactersNoSpaces=50
  assert.equal(calculateOrderPriceTree(node,[price(.1)]).incomplete,true)
})
