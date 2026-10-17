import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeAnnotationOrderLevel, supportsAnnotationGrandchildOrders, supportsAnnotationLanguageRegions, supportsAnnotationRegionFilters } from '../src/utils/annotationOrderCapabilities.js'

test('地区展示与地区筛选分别检测，支持录入的旧后端不误开放新筛选', () => {
  const schema = {components:{schemas:{AnnotationLanguageItemInput:{properties:{regions:{}}}}},paths:{'/projects/annotation/page':{get:{}}}}
  assert.equal(supportsAnnotationLanguageRegions(schema),true)
  assert.equal(supportsAnnotationRegionFilters(schema),false)
  schema.paths['/projects/annotation/page'].get['x-annotation-region-filters']=['city','district','street']
  assert.equal(supportsAnnotationRegionFilters(schema),true)
})

test('后端明确声明语言项地区字段后才开放录入', () => {
  assert.equal(supportsAnnotationLanguageRegions({}), false)
  assert.equal(supportsAnnotationLanguageRegions({ components: { schemas: { AnnotationLanguageItemInput: { properties: { source_language_id: {} } } } } }), false)
  assert.equal(supportsAnnotationLanguageRegions({ components: { schemas: { AnnotationLanguageItemInput: { properties: { regions: { type: 'array' } } } } } }), true)
})

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
