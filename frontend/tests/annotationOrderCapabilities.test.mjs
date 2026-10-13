import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeAnnotationOrderLevel, supportsAnnotationGrandchildOrders } from '../src/utils/annotationOrderCapabilities.js'

test('旧后端和缺失接口定义不得启用片区及三级订单', () => {
  for (const schema of [undefined, {}, { paths: { '/projects/annotation/page': { get: { parameters: [{ name: 'order_scope', schema: { pattern: '^(all|parent|child)$' } }] } } } }]) {
    assert.equal(supportsAnnotationGrandchildOrders(schema), false)
  }
})

test('片区接口与三级订单范围均存在才启用新版功能', () => {
  const paths = { '/projects/annotation/areas': { get: {} }, '/projects/annotation/page': { get: { parameters: [{ name: 'order_scope', schema: { pattern: '^(all|parent|child|grandchild)$' } }] } } }
  assert.equal(supportsAnnotationGrandchildOrders({ paths }), true)
  paths['/projects/annotation/page'].get.parameters[0].schema.pattern = '^(all|parent|child)$'
  assert.equal(supportsAnnotationGrandchildOrders({ paths }), false)
})

test('旧响应按父级关联补齐层级，保留新响应的三级层级和原始对象', () => {
  const legacy = { id: 'child', parentProjectId: 'root' }
  assert.equal(normalizeAnnotationOrderLevel(legacy).orderLevel, 1)
  assert.equal(legacy.orderLevel, undefined)
  assert.equal(normalizeAnnotationOrderLevel({ id: 'root' }).orderLevel, 0)
  assert.equal(normalizeAnnotationOrderLevel({ ...legacy, orderLevel: 2 }).orderLevel, 2)
})
