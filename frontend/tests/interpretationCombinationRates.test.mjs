import test from 'node:test'
import assert from 'node:assert/strict'
import {financeDraft,interpretationFinanceTotals,interpretationFinancePayload,financeSummary} from '../src/utils/interpretationCustomerFinance.js'

test('不同单位组合、倍数加班及独立加班使用相同计价规则',()=>{
 const rates=[{direction:'中文 ↔ 英语',amount:1000,currency:'CNY',unit:'天',quantity:1,tax_prices:{unit_price_excl_tax:1000,unit_price_incl_tax:1100}},{direction:'中文 ↔ 英语',amount:600,currency:'CNY',unit:'半天',quantity:1,tax_prices:{unit_price_excl_tax:600,unit_price_incl_tax:660}}]
 const draft=financeDraft({rates,settlement:{tax_basis:'excl_tax'}})
 assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'1600.00'})
 draft.has_overtime=true;draft.overtime={pricing_mode:'multiplier',base_rate_index:0,multiplier:1.5,quantity:2}
 assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'4600.00'})
 assert.match(financeSummary(draft),/加班费/)
 assert.doesNotMatch(financeSummary(draft),/undefined/)
 draft.overtime={pricing_mode:'rates',rates:[{...draft.rates[0],amount:200,quantity:2,taxPrices:{unitPriceExclTax:200,unitPriceInclTax:220}}]}
 assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'2000.00'})
 const payload=interpretationFinancePayload(draft)
 assert.equal(payload.overtime.amount,0)
 assert.equal(payload.overtime.rates[0].tax_prices.unit_price_excl_tax,200)
})

test('恢复草稿优先保留编辑后的税价，而不是旧接口税价',()=>{
 const draft=financeDraft({rates:[{amount:1000,quantity:1,currency:'CNY',unit:'天',tax_prices:{unit_price_excl_tax:1000},taxPrices:{unitPriceExclTax:1200}}],has_overtime:true,overtime:{pricing_mode:'rates',rates:[{amount:100,quantity:1,currency:'CNY',unit:'小时',tax_prices:{unit_price_excl_tax:100},taxPrices:{unitPriceExclTax:150}}]}})
 assert.equal(draft.rates[0].taxPrices.unitPriceExclTax,1200)
 assert.equal(draft.overtime.rates[0].taxPrices.unitPriceExclTax,150)
})

test('先计算方向小计折扣，再合计并应用合计调整；加班费独立计算',()=>{
 const draft=financeDraft({rates:[{direction:'中英',amount:1000,currency:'CNY',unit:'天',quantity:1,tax_prices:{unit_price_excl_tax:1000},group_adjustments:[{currency:'CNY',excl_discount:90}],combined_adjustments:[{currency:'CNY',excl_amount:1800}]},{direction:'中英',amount:600,currency:'CNY',unit:'半天',quantity:1,tax_prices:{unit_price_excl_tax:600}},{direction:'中日',amount:500,currency:'CNY',unit:'小时',quantity:1,tax_prices:{unit_price_excl_tax:500}}],has_overtime:true,overtime:{pricing_mode:'rates',amount:0,rates:[{direction:'中英',amount:200,currency:'CNY',unit:'小时',quantity:2,tax_prices:{unit_price_excl_tax:200},group_adjustments:[{currency:'CNY',excl_discount:50}]}]},settlement:{tax_basis:'excl_tax'}})
 assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'2000.00'})
 draft.rates[0].combined_adjustments=[]
 assert.deepEqual(interpretationFinanceTotals(draft),{CNY:'2140.00'})
})

test('未填写单价的空白行、空白加班费不提交为新增收费',()=>{
 const draft=financeDraft({rates:[]})
 draft.rates.push({direction:'中英',currency:'CNY',unit:'天',quantity:1,hours:8,taxPrices:{}})
 draft.has_overtime=true;draft.overtime={pricing_mode:'rates',amount:0,currency:'CNY',rates:[]}
 const payload=interpretationFinancePayload(draft)
 assert.deepEqual(payload.rates,[])
 assert.equal(payload.has_overtime,false)
 assert.equal(payload.overtime,null)
})
