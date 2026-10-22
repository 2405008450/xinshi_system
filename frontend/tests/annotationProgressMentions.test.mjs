import test from 'node:test'
import assert from 'node:assert/strict'
import { progressMentionSelection, expandProgressMentionDepartments } from '../src/utils/annotationProgressMentions.js'

test('当前订单所有项目经理优先预选，合并共享名单、去重并排除自己及失效账号',()=>{
  const users=['pm2','pm1','extra','self'].map(id=>({id}))
  const project={roleAssignments:[{roleCode:'project_manager',assigneeId:'pm1'},{roleCode:'client_manager',assigneeId:'customer'},{roleCode:'project_manager',assigneeId:'pm2'},{roleCode:'project_manager',assigneeId:'self'}]}
  assert.deepEqual(progressMentionSelection(['extra','pm1','deleted'],project,users,'self'),['pm1','pm2','extra'])
  assert.deepEqual(progressMentionSelection([],{},users,'self'),[])
  const selected=progressMentionSelection([],project,users,'self');selected.splice(0,1);selected.push('extra')
  assert.deepEqual(progressMentionSelection([],project,users,'self'),['pm1','pm2'])
})

test('本次发送选择部门后展开为人员，允许逐人移除，避免隐藏部门再次添加已移除的人',()=>{
  const users=[{id:'a',departmentId:'d'},{id:'b',departmentId:'d'},{id:'c',departmentId:'other'}]
  const selected=expandProgressMentionDepartments({userIds:['a'],departmentIds:['d']},users)
  assert.deepEqual(selected,{userIds:['a','b'],departmentIds:[]})
  selected.userIds.splice(0,1)
  assert.deepEqual(expandProgressMentionDepartments(selected,users).userIds,['b'])
})

test('跨部门人员通过任一所属部门匹配，多个部门及显式选择同人只展开一次',()=>{
  const users=[{id:'a',departmentId:'old',departmentIds:['old','annotation']},{id:'b',departmentIds:['annotation']},{id:'c',departmentId:'other'}]
  assert.deepEqual(expandProgressMentionDepartments({userIds:['a'],departmentIds:['old','annotation']},users),{userIds:['a','b'],departmentIds:[]})
})
