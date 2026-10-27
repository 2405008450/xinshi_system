import test from 'node:test'
import assert from 'node:assert/strict'
import { collectAdvancedFilterFields, applyAdvancedFilterFieldSearch } from '../src/utils/advancedFilterFieldSearch.js'

function fixture(labels) {
  const root = { querySelectorAll: () => elements, contains: element => elements.includes(element) || elements.some(field => field.column === element) }
  const elements = labels.map(label => ({
    style: {}, hidden: false, parentElement: root, attributes: new Map(),
    getAttribute(key) { return this.attributes.get(key) ?? null },
    setAttribute(key, value) { this.attributes.set(key, value) },
    removeAttribute(key) { this.attributes.delete(key) },
    contains(element) { return element === this },
    querySelector: () => ({ textContent: label }),
    closest() { return this.column || null },
    value: '原有筛选值',
  }))
  root.style = {}
  return { root, elements }
}

test('自动收集实际字段名称，条件隐藏的字段不计数，动态增减后重新识别', () => {
  const { root, elements } = fixture(['人才编号', '姓名', '学历', '语种', '院校', '专业', '性别'])
  assert.equal(collectAdvancedFilterFields(root).length, 7)
  elements[6].style.display = 'none'
  assert.equal(collectAdvancedFilterFields(root).length, 6)
  elements[6].style.display = ''
  assert.equal(collectAdvancedFilterFields(root).length, 7)
  assert.equal(collectAdvancedFilterFields(root)[0].label, '人才编号')
})

test('多关键词只筛选字段呈现；清空后恢复，条件值不会丢失', () => {
  const { root, elements } = fixture(['客户全称', '客户简称', '人才编号'])
  const fields = collectAdvancedFilterFields(root)
  applyAdvancedFilterFieldSearch(fields, '称 客户')
  assert.deepEqual(elements.map(field => field.attributes.has('data-advanced-filter-search-hidden')), [false, false, true])
  // 再次收集不会把刚被搜索隐藏的字段从索引中丢掉。
  assert.equal(collectAdvancedFilterFields(root).length, 3)
  applyAdvancedFilterFieldSearch(fields, '不存在')
  assert.ok(elements.every(field => field.attributes.has('data-advanced-filter-search-hidden')))
  applyAdvancedFilterFieldSearch(fields, '')
  assert.ok(elements.every(field => !field.attributes.has('data-advanced-filter-search-hidden')))
  assert.ok(elements.every(field => field.value === '原有筛选值'))
})

test('单字段栅格列整体隐藏，多个字段共用一列时只隐藏对应字段', () => {
  const { root, elements } = fixture(['姓名', '客户编号'])
  const column = { attributes: new Map(), querySelectorAll: () => [elements[0]], setAttribute(key, value) { this.attributes.set(key, value) }, removeAttribute(key) { this.attributes.delete(key) } }
  elements[0].column = column
  let fields = collectAdvancedFilterFields(root)
  applyAdvancedFilterFieldSearch(fields, '客户')
  assert.equal(column.attributes.has('data-advanced-filter-search-hidden'), true)
  applyAdvancedFilterFieldSearch(fields, '')
  assert.equal(column.attributes.size, 0)
  column.querySelectorAll = () => elements
  fields = collectAdvancedFilterFields(root)
  assert.equal(fields[0].container, elements[0])
})
