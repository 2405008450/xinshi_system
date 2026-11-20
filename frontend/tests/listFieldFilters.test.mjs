import assert from 'node:assert/strict'
import test from 'node:test'
import { BLANK_FILTER_VALUE, buildFieldFilters, countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '../src/utils/listFieldFilters.js'

const definitions = [
  { key: 'operatorName', type: 'text', allowEmpty: true },
  { key: 'fullName', type: 'text' },
]

test('操作人空白条件可序列化、组合、清除及重置', () => {
  const model = createFilterModel(definitions)
  assert.equal(serializeFieldFilters(model, definitions), undefined)
  model.operatorName = { op: 'is_empty' }
  assert.equal(countActiveFilters(model, definitions), 1)
  assert.deepEqual(buildFieldFilters(model, definitions), { operator_name: { op: 'is_empty' } })
  model.fullName = ' 张 '
  assert.deepEqual(JSON.parse(serializeFieldFilters(model, definitions)), {
    operator_name: { op: 'is_empty' }, full_name: { op: 'contains', value: '张' },
  })
  model.operatorName = ''
  assert.deepEqual(buildFieldFilters(model, definitions), { full_name: { op: 'contains', value: '张' } })
  model.operatorName = ' 操作员 '
  assert.deepEqual(buildFieldFilters(model, definitions).operator_name, { op: 'contains', value: '操作员' })
  resetFilterModel(model, definitions)
  assert.equal(countActiveFilters(model, definitions), 0)
  assert.equal(serializeFieldFilters(model, definitions), undefined)
})

test('文本、单选、多选、日期、数值和布尔都可使用空白条件', () => {
  const fields = [
    { key: 'text', type: 'text' }, { key: 'single', type: 'select', multiple: false },
    { key: 'status', type: 'select' }, { key: 'date', type: 'date-range' },
    { key: 'amount', type: 'number-range' }, { key: 'flag', type: 'boolean' },
    { key: 'computed', type: 'select', allowEmpty: false },
  ]
  const model = Object.fromEntries(fields.map(({ key }) => [key, BLANK_FILTER_VALUE]))
  const filters = buildFieldFilters(model, fields)
  assert.equal(countActiveFilters(model, fields), 6)
  assert.deepEqual(Object.values(filters), Array(6).fill({ op: 'is_empty' }))
  model.amount = [0, null]
  model.flag = false
  assert.deepEqual(buildFieldFilters(model, fields).amount, { op: 'between', min: 0, max: null })
  assert.deepEqual(buildFieldFilters(model, fields).flag, { op: 'eq', value: false })
})
