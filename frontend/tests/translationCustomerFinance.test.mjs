import test from 'node:test'
import assert from 'node:assert/strict'
import { calculateCustomerPrice, customerFinanceTotals, customerFinanceUnitPrices, customerFinanceWordCount, customerFinanceChargePayload } from '../src/utils/translationCustomerFinance.js'

test('单字、份、页计价与后端一致，金额以十进制四舍五入',()=>{assert.equal(calculateCustomerPrice('1.005',1),'1.01');assert.equal(calculateCustomerPrice('0.1234',20),'2.47');assert.equal(calculateCustomerPrice('0',100),'0.00');assert.equal(calculateCustomerPrice('100',2000,1000),'200.00');assert.equal(calculateCustomerPrice('1',null),null)})

test('客户财务的原价与调整价独立，区分币种、税制、零金额和固定收费', () => {
  const project = {customerChargeItems:[
    {itemName:'翻译费',currency:'CNY',pricingMode:'metric',calculatedTotalExclTax:'100.00',calculatedTotalInclTax:'106.00',totalExclTax:'90.00',totalInclTax:'95.40'},
    {itemName:'排版费',currency:'CNY',pricingMode:'fixed',totalExclTax:'10.10',totalInclTax:'10.71'},
    {itemName:'测试费',currency:'USD',pricingMode:'fixed',totalInclTax:0},
  ]}
  assert.equal(customerFinanceTotals(project),'CNY（不含税） 110.10\nCNY（含税） 116.71\nUSD（含税） 0.00')
  assert.equal(customerFinanceTotals(project,true),'CNY（不含税） 100.10\nCNY（含税） 106.11\nUSD（含税） 0.00')
  assert.equal(customerFinanceTotals({}),'-')
})
test('未填金额不伪装成完整合计，单价和客户统计保留零值', () => {
  const project={customerChargeItems:[{itemName:'一',currency:'CNY',pricingMode:'fixed',totalInclTax:'0.10'},{itemName:'二',currency:'CNY',pricingMode:'fixed'}]}
  assert.match(customerFinanceTotals(project),/已填 1\/2 项/)
  assert.match(customerFinanceUnitPrices({customerChargeItems:[{itemName:'一',unitPriceInclTax:0,unitSize:1000,metricType:'words'}]}),/含税 CNY 0\/1000字数/)
  assert.equal(customerFinanceWordCount({wordCountMatrix:{customer:{words:0}}}),'字数：0')
})
test('保存仅发送收费输入字段，去掉计算值并保留收费项身份', () => {
  const [item]=customerFinanceChargePayload([{id:'one',itemName:'翻译费',sequenceNo:7,calculatedTotalInclTax:'999',totalInclTax:0,remarks:'折扣说明'}])
  assert.equal(item.id,'one');assert.equal(item.sequenceNo,1);assert.equal(item.totalInclTax,0)
  assert.equal(item.remarks,'折扣说明');assert.equal('calculatedTotalInclTax' in item,false)
})
