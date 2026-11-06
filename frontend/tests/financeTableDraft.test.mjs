import test from 'node:test'
import assert from 'node:assert/strict'
import {financeDraft,financeFieldValue,sameFinanceField} from '../src/utils/financeTableDraft.js'

test('账单月份按订单号生成，覆盖旧收费月份和空值',()=>{
  assert.equal(financeDraft({orderNo:'TP-261025-003',billingMonth:'2026-11'}).billingMonth,'2026-10')
  assert.equal(financeDraft({orderNo:'TP-261025-002.001',billingMonth:null}).billingMonth,'2026-10')
  assert.equal(financeDraft({orderNo:'TP-20261025-001'}).billingMonth,'2026-10')
})

test('空单价保持为空，零金额和空金额独立',()=>{
  assert.deepEqual(financeDraft({languagePair:'中→英',prices:[]}).prices,[])
  assert.equal(financeFieldValue('adjustedTotal',0),0)
  assert.equal(financeFieldValue('adjustedTotal',''),null)
})

test('单价比较忽略新保存的收费项 ID 和独立总价，保留单价变化',()=>{
  const before=[{id:null,languagePair:'中→英',currency:'CNY',metric:'customer_auto',unitSize:1,taxPrices:{unitPriceExclTax:0,unitPriceInclTax:null}}]
  const after=[{...before[0],id:'saved',taxPrices:{...before[0].taxPrices,totalExclTax:100}}]
  assert.equal(sameFinanceField('prices',before,after),true)
  after[0].taxPrices.unitPriceExclTax=0.2
  assert.equal(sameFinanceField('prices',before,after),false)
})
