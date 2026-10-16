import test from 'node:test'
import assert from 'node:assert/strict'
import { managerChanges, sameManagers } from '../src/utils/annotationManagerChange.js'
import { convertAnnotationKeys } from '../src/utils/annotationStatus.js'

const row = (ids = [], client = null, history = {}) => ({ clientManagerId: client,
  roleAssignments: ids.map(id => ({roleCode:'project_manager',assigneeId:id})), managerAssignmentHistory: history })

test('两类经理分别判断首次分配，多人一次添加可免原因', () => {
  const changes = managerChanges(row(), row(['a','b'],'c'))
  assert.equal(changes.length, 2)
  assert.ok(changes.every(item => !item.requiresReason))
  assert.equal(managerChanges(row(['a']),row(['a'],'c'))[0].requiresReason, false)
})

test('增减替换及清空后再次添加都要求原因，顺序变化不算变更', () => {
  for (const ids of [[], ['b'], ['a','b']]) assert.equal(managerChanges(row(['a']),row(ids))[0].requiresReason, true)
  assert.equal(managerChanges(row([],null,{project_manager:true}),row(['a']))[0].requiresReason, true)
  assert.equal(managerChanges(row([],null,{client_manager:true}),row([],'c'))[0].requiresReason, true)
  assert.deepEqual(managerChanges(row(['a','b']),row(['b','a'])), [])
  assert.equal(sameManagers(['a'],['b']), false)
})

test('历史状态业务键经过接口转换后仍可判断清空后的重新分配', () => {
  const detail = convertAnnotationKeys({manager_assignment_history:{project_manager:true,client_manager:false},role_assignments:[]}, key => key.replace(/_([a-z])/g,(_,char)=>char.toUpperCase()))
  assert.equal(managerChanges(detail,row(['a']))[0].requiresReason,true)
  assert.equal(managerChanges(detail,row([],'c'))[0].requiresReason,false)
})
