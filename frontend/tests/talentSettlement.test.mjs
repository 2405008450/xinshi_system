import test from 'node:test'
import assert from 'node:assert/strict'
import { emptySettlement,settlementForm,settlementCategoryOptions,settlementUnitOptions,settlementCurrencyOptions,newSettlementPrice,settlementPriceAmount,settlementPriceSource } from '../src/utils/talentSettlement.js'

test('结算默认独立并将接口字符串金额转换为数字控件值',()=>{
  const a=emptySettlement(),b=emptySettlement()
  a.prices.push({amount:1})
  assert.equal(b.prices.length,0)
  assert.equal(settlementForm({bankAccount:'001234',prices:[{amount:'0.123456'}]}).prices[0].amount,0.123456)
  assert.equal(settlementForm({bankAccount:'001234'}).bankAccount,'001234')
})
test('价格类型兼容旧四项并扩展币种和独立计价口径',()=>{
  assert.deepEqual(settlementCategoryOptions.map(item=>item.label),['口译','笔译','标注','采集'])
  assert.deepEqual(settlementCurrencyOptions.map(item=>item.value),['CNY','USD','HKD','EUR','GBP','BRL','IDR'])
  for(const unit of ['word','character','per_word','source_word','target_word','month','occurrence','item','work_hour','effective_hour'])assert.ok(settlementUnitOptions.some(item=>item.value===unit))
})

test('新报价币种留空，旧报价兼容默认值，原文和来源往返完整',()=>{
  const quote=newSettlementPrice()
  assert.equal(quote.status,'pending');assert.equal(quote.currency,null)
  const raw={...quote,amount:'0.025',amountMax:'0.05',priceType:'range',serviceType:'proofreading',languagePair:'EN-AR',rawText:'翻译 $0.05\n校对 $0.025',sourceFile:'共培.xlsx',sourceSheet:'共培总表',sourceRow:9,sourceColumn:'每字',notes:'币种待核'}
  const actual=settlementForm({prices:[raw]}).prices[0]
  assert.equal(actual.amount,0.025);assert.equal(actual.amountMax,0.05);assert.equal(actual.currency,null)
  for(const field of ['rawText','sourceFile','sourceSheet','sourceRow','sourceColumn','notes','languagePair','serviceType'])assert.equal(actual[field],raw[field])
  assert.equal(settlementForm({prices:[{amount:1}]}).prices[0].currency,'CNY')
  assert.equal(settlementForm({prices:[{status:'pending',rawText:'120'}]}).prices[0].currency,null)
  assert.equal(settlementPriceAmount(actual),'0.025 ～ 0.05')
  assert.equal(settlementPriceAmount({priceType:'negotiable',amount:null}),'可协商')
  assert.equal(settlementPriceAmount({amount:0}),'0')
  assert.equal(settlementPriceSource(actual),'共培.xlsx / 共培总表 / 第 9 行 / 每字')
})
