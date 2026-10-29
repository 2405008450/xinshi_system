import test from 'node:test'
import assert from 'node:assert/strict'
import { emptySettlement,settlementForm,settlementCategoryOptions,settlementUnitOptions,settlementCurrencyOptions } from '../src/utils/talentSettlement.js'

test('结算默认独立并将接口字符串金额转换为数字控件值',()=>{
  const a=emptySettlement(),b=emptySettlement()
  a.prices.push({amount:1})
  assert.equal(b.prices.length,0)
  assert.equal(settlementForm({bankAccount:'001234',prices:[{amount:'0.123456'}]}).prices[0].amount,0.123456)
  assert.equal(settlementForm({bankAccount:'001234'}).bankAccount,'001234')
})
test('价格类型四项、货币沿用系统五项并包含现有计费单位',()=>{
  assert.deepEqual(settlementCategoryOptions.map(item=>item.label),['口译','笔译','标注','采集'])
  assert.deepEqual(settlementCurrencyOptions.map(item=>item.value),['CNY','USD','HKD','EUR','GBP'])
  for(const unit of ['occurrence','item','work_hour','effective_hour'])assert.ok(settlementUnitOptions.some(item=>item.value===unit))
})
