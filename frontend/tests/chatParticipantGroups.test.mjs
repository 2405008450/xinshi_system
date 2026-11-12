import test from 'node:test'
import assert from 'node:assert/strict'
import { participantGroups, toggleParticipantSelection } from '../src/utils/chatParticipantGroups.js'
const users = [{ id: 1, name: '甲' }, { id: 2, name: '乙' }, { id: 3, name: '丙' }, { id: 4, name: '丁' }]
const directory = {
  aliases: { 技术: 'IT部' }, items: [{ name: 'IT部' }, { name: '项目部' }],
  people: [
    { id: '1', username: 'alpha', primaryDepartment: 'IT部', departments: [{ name: '技术' }, { name: '项目部' }] },
    { id: '2', departments: [{ name: '项目部' }] },
    { id: '9', name: '无邀请权限', departments: [{ name: 'IT部' }] },
  ],
}
test('按主部门及跨部门归属分组，合并别名，排除现有成员和无邀请权限人员', () => {
  const groups = participantGroups([...users, users[0]], [{ id: '2' }], directory)
  assert.deepEqual(groups.map(g => [g.name, g.people.map(p => p.id)]), [['IT部', [1]], ['项目部', [1]], ['未分配部门', [3, 4]]])
})
test('可按部门、姓名及账号搜索，搜索后整组选中仅包含匹配人员', () => {
  assert.deepEqual(participantGroups(users, [], directory, 'alpha').flatMap(g => g.people.map(p => p.id)), [1, 1])
  assert.deepEqual(participantGroups(users, [], directory, '项目部 乙').map(g => g.people.map(p => p.id)), [[2]])
  assert.deepEqual(participantGroups(users, [], directory, '不存在'), [])
})
test('整部门合并选择去重，跨部门共享人员不会重复提交', () => {
  let selection = toggleParticipantSelection([], [users[0], users[1]], true)
  selection = toggleParticipantSelection(selection, [users[0], users[2]], true)
  assert.deepEqual(selection, [1, 2, 3])
  assert.deepEqual(toggleParticipantSelection(selection, [users[0], users[2]], false), [2])
})
test('名册加载失败仍保留全部可邀请人员，不生成多余人员', () => {
  assert.deepEqual(participantGroups(users, [], {}).map(g => g.people.length), [4])
  assert.deepEqual(toggleParticipantSelection(['1'], [users[0]], true), [1])
})
