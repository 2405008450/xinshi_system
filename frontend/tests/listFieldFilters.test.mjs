import assert from 'node:assert/strict'
import test from 'node:test'
import { buildFieldFilters, countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '../src/utils/listFieldFilters.js'

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
