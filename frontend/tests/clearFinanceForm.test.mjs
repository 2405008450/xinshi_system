import test from 'node:test'
import assert from 'node:assert/strict'
import {clearFinanceForm} from '../src/utils/clearFinanceForm.js'

test('清空财务填写，保留项目、统计及付款修订号，待保存',()=>{
  const source={id:'order',rootId:'root',orderNo:'TP-261025-003',languagePair:'中→英',wordCountMatrix:{customer:{words:100}},pricingMode:'fixed',adjustedTotal:200,explanation:'内部',customerExplanation:'客户',statementRequired:true,quotationRequired:true,paymentConfirmation:{revision:4,isPaid:true,paymentOption:'full',fullPaymentAmount:200,proofs:'凭证'}}
  const cleared=clearFinanceForm(source,direction=>({languagePair:direction,taxPrices:{}}))
  assert.equal(cleared.adjustedTotal,undefined);assert.equal(cleared.explanation,'');assert.equal(cleared.customerExplanation,'')
  assert.equal(cleared.statementRequired,false);assert.equal(cleared.statementRequiredDirty,true)
  assert.equal(cleared.paymentConfirmation.clearDetails,true);assert.equal(cleared.paymentConfirmation.revision,4)
  assert.equal(cleared.paymentConfirmation.proofs,'');assert.equal(cleared.paymentConfirmation.isPaid,false)
  assert.deepEqual(cleared.wordCountMatrix,source.wordCountMatrix);assert.equal(cleared.orderNo,source.orderNo)
  assert.equal(source.adjustedTotal,200);assert.equal(source.paymentConfirmation.proofs,'凭证')
})

test('父订单只清空可编辑信息，保留下级汇总数据',()=>{
  const source={priceAggregate:true,prices:[{amount:.1}],children:[{id:'child'}],explanation:'备注'}
  const cleared=clearFinanceForm(source,()=>({}))
  assert.deepEqual(cleared.prices,source.prices);assert.deepEqual(cleared.children,source.children)
  assert.equal(cleared.explanation,'')
})
