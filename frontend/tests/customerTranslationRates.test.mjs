import test from 'node:test'
import assert from 'node:assert/strict'
import {defaultRateMetric,newCustomerRate,ratePayload,referenceDraft} from '../src/utils/customerTranslationRates.js'
test('按翻译方向选择默认统计口径，新增价格默认人民币',()=>{
  assert.equal(defaultRateMetric('英语（美国）→简体中文'),'customer_auto')
  assert.equal(defaultRateMetric('简中→英语'),'customer_auto')
  assert.equal(defaultRateMetric('日语→繁體中文'),'customer_auto')
  assert.equal(newCustomerRate('英语→简中').currency,'CNY')
})
test('客户参考价带入为未保存草稿，保留参考版本并不把参考价ID误当订单收费项ID',()=>{
  const draft=referenceDraft({id:'reference',languagePair:'英语→简中',amount:'.1',currency:'USD',metric:'foreign_words',unitSize:'1000',revision:3})
  const payload=ratePayload(draft)
  assert.equal(payload.id,null);assert.equal(payload.reference_id,'reference');assert.equal(payload.reference_revision,3)
  assert.equal(payload.amount,.1);assert.equal(payload.unit_size,1000);assert.equal(payload.currency,'USD')
})
