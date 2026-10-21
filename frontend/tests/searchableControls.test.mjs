import test from 'node:test'
import assert from 'node:assert/strict'
import { h, Fragment } from 'vue'
import { ElOption, ElOptionGroup } from 'element-plus'
import { filterSearchOptions } from '../src/components/common/searchableControls.js'

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
