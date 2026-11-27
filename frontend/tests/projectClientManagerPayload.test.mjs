import test from 'node:test'
import assert from 'node:assert/strict'
import {projectClientManagerPayload} from '../src/utils/projectClientManagerPayload.js'

test('新增默认提交填写人，编辑译员时不重复提交未变更的客户经理',()=>{
  const form={clientManagerId:'manager',currentClientManager:'赵震锋',clientManagerChangeReason:'',interpreterAssignments:[{translatorId:'talent'}]}
  assert.deepEqual(projectClientManagerPayload(form,'manager',true),{clientManagerId:'manager',clientManagerChangeReason:null})
  assert.deepEqual(projectClientManagerPayload(form,'manager'),{})
  assert.deepEqual(projectClientManagerPayload({clientManagerId:''},''),{})
})

test('主动更换和清空客户经理仍提交变更及原因，不提交显示姓名',()=>{
  assert.deepEqual(projectClientManagerPayload({clientManagerId:' new ',clientManagerChangeReason:' 客户交接 ',currentClientManager:'旧经理'},'old'),{clientManagerId:'new',clientManagerChangeReason:'客户交接'})
  assert.deepEqual(projectClientManagerPayload({clientManagerId:'',clientManagerChangeReason:'解除分配'},'old'),{clientManagerId:null,clientManagerChangeReason:'解除分配'})
})
