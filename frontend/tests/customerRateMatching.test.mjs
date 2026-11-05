import test from 'node:test'
import assert from 'node:assert/strict'
import {priceMatch,replaceMatchedReference} from '../src/utils/customerRateMatching.js'
const price={languagePair:'中→英',metric:'company_words',currency:'CNY',unitSize:1}
const reference={...price,metric:'customer_auto:words'}
test('来源可不同，但实际单位、方向、币种及计价数量必须全匹配',()=>{
 assert.equal(priceMatch(reference,price,{}).matched,true)
 for(const change of [{metric:'customer_auto:pages'},{currency:'USD'},{unitSize:1000},{languagePair:'英→中'},{metric:'customer_auto'}])assert.equal(priceMatch({...reference,...change},price,{}).matched,false)
 assert.equal(priceMatch(reference,{...price,metric:'customer_auto'},{customer:{words:20}}).matched,true)
 assert.equal(priceMatch(reference,{...price,metric:'customer_auto'},{company:{pages:3}}).matched,false)
 assert.equal(replaceMatchedReference([price],reference,{}),0)
 assert.throws(()=>replaceMatchedReference([price],{...reference,unitSize:1000},{}))
})
