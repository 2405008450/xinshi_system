import test from 'node:test'
import assert from 'node:assert/strict'
import {emptyProjectContactDetails,projectContactPayload} from '../src/utils/projectClientContacts.js'

test('未完成客户资料加载时不提交空联系方式覆盖历史数据',()=>{
  assert.deepEqual(projectContactPayload(emptyProjectContactDetails()),{})
})
test('受限用户只提交联系人说明和版本，授权用户才能提交联系方式',()=>{
  const form={...emptyProjectContactDetails(),clientContactMethod:'phone',clientContactDescription:'采购负责人',clientContactVersion:'v1'}
  assert.deepEqual(projectContactPayload(form),{clientContactDescription:'采购负责人',clientContactVersion:'v1'})
  assert.equal(projectContactPayload({...form,clientContactsVisible:true}).clientContactMethod,'phone')
})
