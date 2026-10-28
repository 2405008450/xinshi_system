import test from 'node:test'
import assert from 'node:assert/strict'
import { h, Fragment } from 'vue'
import { ElOption, ElOptionGroup } from 'element-plus'
import { filterSearchOptions, SearchSelect, SearchCascader, SearchTransfer } from '../src/components/common/searchableControls.js'

function renderControl(component, attrs = {}, slots = {}) {
  return component.setup({}, { attrs, slots, expose() {} })
}

test('可搜索多选默认清空关键词，兼容显式的两种属性写法', () => {
  const attrs = { multiple: true, filterable: true }
  assert.equal(renderControl(SearchSelect, attrs)().props.reserveKeyword, false)
  for (const key of ['reserveKeyword', 'reserve-keyword']) {
    for (const value of [true, false, '']) {
      const props = renderControl(SearchSelect, { ...attrs, [key]: value })().props
      assert.equal(props[key], value)
      const otherKey = key === 'reserveKeyword' ? 'reserve-keyword' : 'reserveKeyword'
      assert.equal(Object.hasOwn(props, otherKey), false)
    }
  }
})

test('底层清空查询时恢复全部候选项，保留选中值和事件', () => {
  const selected = ['严韵']
  const onChange = () => {}
  const render = renderControl(SearchSelect, { multiple: true, filterable: true, modelValue: selected, onChange }, {
    default: () => ['严韵', '刘峰'].map(value => h(ElOption, { value, label: value, key: value })),
  })
  render().props.filterMethod('严')
  assert.deepEqual(render().children.default().map(node => node.props.value), ['严韵'])
  render().props.filterMethod('')
  const restored = render()
  assert.deepEqual(restored.children.default().map(node => node.props.value), ['严韵', '刘峰'])
  assert.equal(restored.props.modelValue, selected)
  assert.equal(restored.props.onChange, onChange)
})

test('远程和自定义过滤仍由调用方负责，其他控件不注入多选配置', () => {
  const filterMethod = () => {}
  const remoteMethod = () => {}
  const remote = renderControl(SearchSelect, { multiple: true, filterable: true, remote: true, remoteMethod })()
  assert.equal(remote.props.reserveKeyword, false)
  assert.equal(remote.props.remoteMethod, remoteMethod)
  assert.equal(remote.props.filterMethod, undefined)
  assert.equal(renderControl(SearchSelect, { filterable: true, filterMethod })().props.filterMethod, filterMethod)
  assert.equal(renderControl(SearchSelect, { filterable: true, 'filter-method': filterMethod })().props['filter-method'], filterMethod)
  for (const component of [SearchCascader, SearchTransfer]) {
    assert.equal(Object.hasOwn(renderControl(component, { filterable: true })().props, 'reserveKeyword'), false)
  }
})

test('下拉分组和 v-for Fragment 过滤选项，保留顺序、键和值', () => {
  const options = ['AABB', 'AAA BBB', 'only AA'].map(value => h(ElOption, { value, label: value, key: value }))
  const input = [h(ElOptionGroup, { label: '组' }, { default: () => [h(Fragment, null, options)] })]
  const filtered = filterSearchOptions(input, 'AA BB')[0].children.default()[0].children
  assert.deepEqual(filtered.map(node => node.props.value), ['AABB', 'AAA BBB'])
  assert.deepEqual(filtered.map(node => node.key), ['AABB', 'AAA BBB'])
  assert.equal(input[0].children.default()[0].children.length, 3)
  assert.equal(filterSearchOptions(options, '% _').length, 0)
  assert.equal(filterSearchOptions(options, '').length, 3)
})
