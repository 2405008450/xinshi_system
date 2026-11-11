import test from 'node:test'
import assert from 'node:assert/strict'
import {projectFinanceFields} from '../src/utils/projectFinanceFields.js'

test('编辑已保存项目不回写旧财务副本，避免覆盖另一入口的清空结果',()=>{
  const loaded={projectName:'项目改名',customerChargeItems:[{totalExclTax:330}],paymentConfirmation:{isPaid:true},paymentDraft:[{actual_amount:330}],paymentVersion:'old',wordCountMatrix:{words:100}}
  assert.deepEqual(projectFinanceFields(loaded,true),{projectName:'项目改名',wordCountMatrix:{words:100}})
  assert.equal(loaded.customerChargeItems[0].totalExclTax,330)
})
test('新增母订单与子订单保留随项目提交的财务草稿',()=>{
  const draft={customerChargeItems:[{unitPriceExclTax:.2}],paymentConfirmation:{isPaid:false}}
  assert.deepEqual(projectFinanceFields(draft,false),draft)
})
