import test from 'node:test'
import assert from 'node:assert/strict'

import {
  WORKBENCH_PAGE_SIZE_OPTIONS,
  clearWorkbenchFilterKeys,
  countActiveWorkbenchFilterGroups,
  getWorkbenchFilterStorageKey,
  getWorkbenchLastPage,
  matchesWorkbenchFilterGroups,
  paginateWorkbenchRows,
  workbenchFieldsInclude,
} from '../src/utils/workbenchList.js'

test('工作台分页支持 10、20、50 条并能修正末页', () => {
  const rows = Array.from({ length: 88 }, (_, index) => index + 1)
  assert.deepEqual(WORKBENCH_PAGE_SIZE_OPTIONS, [10, 20, 50])
  assert.deepEqual(paginateWorkbenchRows(rows, 2, 10), rows.slice(10, 20))
  assert.equal(paginateWorkbenchRows(rows, 2, 20).length, 20)
  assert.equal(paginateWorkbenchRows(rows, 2, 50).length, 38)
  assert.equal(getWorkbenchLastPage(88, 10), 9)
  assert.equal(getWorkbenchLastPage(0, 10), 1)
})

test('工作台关键词覆盖项目、订单及客户字段且忽略大小写', () => {
  const row = { order_no: 'TP-260903-005', project_name: 'Notary Review', client_short_name: '新加坡客户' }
  assert.equal(workbenchFieldsInclude(row, ['order_no', 'project_name'], 'notary'), true)
  assert.equal(workbenchFieldsInclude(row, ['client_short_name'], '新加坡'), true)
  assert.equal(workbenchFieldsInclude(row, ['order_no', 'project_name'], '不存在'), false)
})

test('高级筛选数量按条件组统计而不是按多选项数量统计', () => {
  const filters = { project_types: ['translation', 'annotation'], assignees: ['u1'], language_pair: '', risk_states: ['overdue'] }
  assert.equal(countActiveWorkbenchFilterGroups(filters, ['project_types', 'assignees', 'language_pair', 'risk_states']), 3)
})

test('筛选字段组之间使用 AND，同字段多选使用 OR', () => {
  const rows = [
    { project_type: 'translation', status: 'confirmed', client_name: '甲客户' },
    { project_type: 'annotation', status: 'project_in_progress', client_name: '甲客户' },
    { project_type: 'interpretation', status: 'in_progress', client_name: '乙客户' },
  ]
  const filters = { project_types: ['translation', 'annotation'], client: '甲' }
  const matched = rows.filter(row => matchesWorkbenchFilterGroups(row, filters, {
    textFields: { client: ['client_name'] },
    multiValueGetters: { project_types: item => item.project_type },
  }))
  assert.deepEqual(matched, rows.slice(0, 2))
})

test('筛选持久化键按页面和当前用户隔离，空用户使用匿名空间', () => {
  assert.equal(getWorkbenchFilterStorageKey('my-tasks', 'u1'), 'workbench-filters:my-tasks:u1')
  assert.equal(getWorkbenchFilterStorageKey('my-tasks', 'u2'), 'workbench-filters:my-tasks:u2')
  assert.equal(getWorkbenchFilterStorageKey('management-projects', ''), 'workbench-filters:management-projects:anonymous')
})

test('重置清空指定筛选，不影响未列入的条件', () => {
  const filters = { project_types: ['translation'], client: '甲客户', project: '公证', keep: '保留' }
  clearWorkbenchFilterKeys(filters, ['project_types', 'client', 'project'])
  assert.deepEqual(filters, { project_types: [], client: '', project: '', keep: '保留' })
})
