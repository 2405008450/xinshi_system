import test from 'node:test'
import assert from 'node:assert/strict'
import { projectMentionOrder } from '../src/utils/projectMentionOrder.js'

const users = [{ id: '__all__', all: true }, { id: 'ordinary', name: '普通成员' },
  { id: 'client', name: '客户经理' }, { id: 'pm1', name: '项目经理甲' },
  { id: 'outside', name: '未参与人员', outside: true }, { id: 'pm2', name: '项目经理乙', outside: true }]
const project = { clientManagerId: 'client', roleAssignments: [
  { roleCode: 'project_manager', assigneeId: 'pm1' },
  { role_code: 'project_manager', assignee_id: 'pm2' },
] }

test('标注项目的全部项目经理最前、客户经理其次，保留所有人和其他候选的稳定顺序', () => {
  const ordered = projectMentionOrder(users, project)
  assert.deepEqual(ordered.map(user => user.id), ['pm1', 'pm2', 'client', '__all__', 'ordinary', 'outside'])
  assert.deepEqual(ordered.slice(0, 3).map(user => user.mentionSection), ['项目经理', '项目经理', '客户经理'])
  assert.equal(ordered[1].outside, true)
  assert.equal(users[0].id, '__all__')
})

test('兼任两类经理只出现一次，不能把不在可提及名单的人员加入候选', () => {
  const detail = { ...project, clientManagerId: 'pm1', roleAssignments: [...project.roleAssignments, { roleCode: 'project_manager', assigneeId: 'not-eligible' }] }
  const ordered = projectMentionOrder([...users, users[3]], detail)
  assert.equal(ordered.filter(user => user.id === 'pm1').length, 1)
  assert.equal(ordered.some(user => user.id === 'not-eligible'), false)
  assert.equal(ordered[0].mentionSection, '项目经理')
})

test('未加载项目及其他模块维持原列表；旧单项目经理字段可兼容，明确清空经理时不回填', () => {
  assert.equal(projectMentionOrder(users, null), users)
  assert.equal(projectMentionOrder(users, { projectManagerId: 'pm1' })[0].id, 'pm1')
  assert.equal(projectMentionOrder(users, { projectManagerId: 'pm1', roleAssignments: [] })[0].id, '__all__')
})

test('搜索后的候选仍按经理顺序排列，没有匹配经理时照常展示其余人员', () => {
  assert.deepEqual(projectMentionOrder(users.filter(user => user.name?.includes('经理')), project).map(user => user.id), ['pm1', 'pm2', 'client'])
  assert.deepEqual(projectMentionOrder(users.filter(user => user.id === 'ordinary'), project).map(user => user.id), ['ordinary'])
})
