import assert from 'node:assert/strict'
import test from 'node:test'
import { annotationInternalRolesText } from '../src/utils/annotationInternalRoles.js'

test('实际负责人和十二条空占位共存时，每个角色只显示一次', () => {
  const empty = { roleCode: 'project_manager', assigneeId: null, assigneeName: null }
  assert.equal(annotationInternalRolesText({ roleAssignments: [
    empty, { roleCode: 'project_manager', assigneeId: 'ethan', assigneeName: 'Ethan' },
    ...Array(11).fill(empty), { roleCode: 'project_specialist' }, { roleCode: 'project_assistant' },
  ] }), '项目经理：Ethan；项目专员：未分配；项目助理：未分配')
})

test('多人经理保留不同人员，同人重复去除；同名不同账号保留', () => {
  const first = { roleCode: 'project_manager', assigneeId: 'a', assigneeName: '经理甲' }
  assert.equal(annotationInternalRolesText({ roleAssignments: [first, first,
    { ...first, assigneeId: 'b' }, { ...first, assigneeId: 'c', assigneeName: '经理乙' },
  ] }), '项目经理：经理甲、经理甲、经理乙')
})

test('只有空记录时只显示一次未分配；无角色数据时显示横线', () => {
  assert.equal(annotationInternalRolesText({ roleAssignments: Array(12).fill({ roleCode: 'project_manager' }) }), '项目经理：未分配')
  assert.equal(annotationInternalRolesText({}), '-')
})
