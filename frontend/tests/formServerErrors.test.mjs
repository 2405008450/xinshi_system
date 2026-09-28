import assert from 'node:assert/strict'
import test from 'node:test'
import { resolveServerFieldErrors } from '../src/utils/formServerErrors.js'

test('422 错误保留行索引并兼容接口下划线与表单驼峰路径', () => {
  const fields = [{ prop: ['items', '0', 'unitPrice'] }, { prop: ['items', '1', 'unitPrice'] }]
  const result = resolveServerFieldErrors({ rawDetail: [{ loc: ['body', 'items', 1, 'unit_price'], msg: '单价必须大于零' }] }, fields)
  assert.equal(result.matches.length, 1)
  assert.equal(result.matches[0].field, fields[1])
  assert.equal(result.matches[0].message, '单价必须大于零')
})

test('结构化错误使用显式别名，不把其他行的同名字段当作目标', () => {
  const field = { prop: 'amount', label: '人员价格' }
  const result = resolveServerFieldErrors({ rawDetail: { message: '请补齐单位', fieldErrors: [{ path: 'unit', message: '请选择计价单位' }] } }, [field], { unit: 'amount' })
  assert.equal(result.matches[0].field, field)
  assert.equal(resolveServerFieldErrors({ rawDetail: { fieldErrors: [{ path: 'items.9.amount', message: '错误' }] } }, [field]).matches.length, 0)
})

test('旧标签必须唯一完整匹配，不能按部分名称跳转', () => {
  const error = { rawDetail: { message: '报价错误', fieldLabel: '报价金额' } }
  assert.equal(resolveServerFieldErrors(error, [{ prop: 'quoteAmount', label: '报价金额' }]).matches.length, 1)
  assert.equal(resolveServerFieldErrors(error, [{ prop: 'a', label: '报价金额' }, { prop: 'b', label: '报价金额' }]).matches.length, 0)
  assert.equal(resolveServerFieldErrors(error, [{ prop: 'a', label: '客户报价金额' }]).matches.length, 0)
})

test('非表单错误和没有目标的错误只展示表单级提示', () => {
  assert.equal(resolveServerFieldErrors({ rawDetail: [{ loc: ['query', 'name'], msg: '参数错误' }] }, [{ prop: 'name' }]).matches.length, 0)
  const result = resolveServerFieldErrors({ detail: '关联数据已变更，请重新打开' }, [{ prop: 'name' }])
  assert.equal(result.matches.length, 0)
  assert.equal(result.message, '关联数据已变更，请重新打开')
})
