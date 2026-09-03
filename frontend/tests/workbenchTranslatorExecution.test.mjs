import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'

import { useTableColumns } from '../src/composables/useTableColumns.js'
import {
  filterTranslatorExecutionItems,
  getAttentionTranslatorEntries,
  getTranslatorExecutionRiskRank,
  getWorkbenchExecutionDefaultColumnKeys,
  getWorkbenchTaskKey,
  reconcileTranslatorExpandedKeys,
} from '../src/utils/workbenchTranslatorExecution.js'

function task(overrides = {}) {
  return {
    source_kind: 'manuscript_responsibility',
    source_id: 21,
    translator_execution: {
      attention_count: 1,
      overdue_count: 0,
      next_return_time: '2026-09-03 18:00:00',
      items: [],
    },
    ...overrides,
  }
}

test('项目助理默认显示新增列，其他角色默认隐藏但字段仍可配置', () => {
  const columns = [
    { key: 'orderNo' },
    { key: 'translatorReturn' },
    { key: 'taskCompletion' },
  ]
  assert.deepEqual(
    getWorkbenchExecutionDefaultColumnKeys(columns, true),
    ['orderNo', 'translatorReturn', 'taskCompletion'],
  )
  assert.deepEqual(getWorkbenchExecutionDefaultColumnKeys(columns, false), ['orderNo'])
})

test('执行层字段配置按当前用户持久化并可在重新进入时恢复', async () => {
  const values = new Map([['user_id', 'assistant-1']])
  globalThis.localStorage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  }
  const columns = [
    { key: 'orderNo' },
    { key: 'translatorReturn' },
    { key: 'taskCompletion' },
  ]
  const first = useTableColumns(
    'workbench-execution-v1',
    columns,
    ['orderNo', 'translatorReturn', 'taskCompletion'],
  )
  first.selectedKeys.value = ['orderNo', 'taskCompletion']
  await nextTick()

  assert.equal(
    values.get('table-columns:workbench-execution-v1:assistant-1'),
    JSON.stringify(['orderNo', 'taskCompletion']),
  )
  const restored = useTableColumns('workbench-execution-v1', columns, ['orderNo'])
  assert.deepEqual(restored.selectedKeys.value, ['orderNo', 'taskCompletion'])
})

test('默认只显示已发译员的待跟进订单，查看全部时恢复完整明细', () => {
  const row = task({
    translator_execution: {
      attention_count: 1,
      items: [
        { entity_id: 1, status: 'translator_returned', needs_attention: false },
        { entity_id: 2, status: 'sent_to_translator', needs_attention: true },
        { entity_id: 3, status: 'confirmed', needs_attention: false },
      ],
    },
  })
  assert.deepEqual(filterTranslatorExecutionItems(row).map(item => item.entity_id), [2])
  assert.deepEqual(filterTranslatorExecutionItems(row, true).map(item => item.entity_id), [1, 2, 3])
})

test('风险顺序为已逾期、24 小时内、其他待回稿、无需跟进', () => {
  const now = new Date('2026-09-03T10:00:00+08:00')
  const rows = [
    task({ source_id: 4, translator_execution: { attention_count: 0, overdue_count: 0 } }),
    task({ source_id: 3, translator_execution: { attention_count: 1, overdue_count: 0, next_return_time: null } }),
    task({ source_id: 2, translator_execution: { attention_count: 1, overdue_count: 0, next_return_time: '2026-09-04 09:00:00' } }),
    task({ source_id: 1, translator_execution: { attention_count: 1, overdue_count: 1, next_return_time: '2026-09-03 09:00:00' } }),
  ]
  rows.sort((left, right) => getTranslatorExecutionRiskRank(left, now) - getTranslatorExecutionRiskRank(right, now))
  assert.deepEqual(rows.map(row => row.source_id), [1, 2, 3, 4])
})

test('待跟进任务自动展开，手动收起后刷新不强制展开，新任务仍会展开', () => {
  const first = task({ source_id: 1 })
  const second = task({ source_id: 2 })
  const firstKey = getWorkbenchTaskKey(first)
  const secondKey = getWorkbenchTaskKey(second)

  assert.deepEqual(reconcileTranslatorExpandedKeys([first], [], new Set()), [firstKey])
  assert.deepEqual(reconcileTranslatorExpandedKeys([first], [], new Set([firstKey])), [])
  assert.deepEqual(
    reconcileTranslatorExpandedKeys([first, second], [], new Set([firstKey])),
    [secondKey],
  )
})

test('最早有效回稿时间优先，未设置时间排在最后', () => {
  const row = task({
    translator_execution: {
      attention_count: 1,
      items: [{
        order_no: 'XS-001-1',
        needs_attention: true,
        assigned_translators: [
          { translator_name: '未定时间', translator_return_time: null },
          { translator_name: '成鹤', translator_return_time: '2026-09-02 19:00:00' },
        ],
      }],
    },
  })
  assert.equal(getAttentionTranslatorEntries(row)[0].translatorName, '成鹤')
})
