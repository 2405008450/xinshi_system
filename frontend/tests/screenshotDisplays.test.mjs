import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import test from 'node:test'
import { createSSRApp, createCommentVNode, createTextVNode, Fragment, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { ElDescriptionsItem } from 'element-plus'

// 仅隔离授权图片的网络请求，详情布局使用真实 Vue 与 Element Plus 渲染。
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === './ScreenshotText.vue') return { url: 'mock:screenshot-display', shortCircuit: true }
    if (specifier === '@/utils/screenshotReferences') {
      return nextResolve(new URL('../src/utils/screenshotReferences.js', import.meta.url).href, context)
    }
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    if (url === 'mock:screenshot-display') return {
      format: 'module', shortCircuit: true,
      source: `import { h } from ${JSON.stringify(import.meta.resolve('vue'))}; export default { props: ['text'], setup: props => () => h('span', { class: 'screenshot-test-preview' }, props.text) }`,
    }
    return nextLoad(url, context)
  },
})
const { ScreenshotDescriptions, ScreenshotTableColumn } = await import('../src/components/common/screenshotDisplays.js')
hooks.deregister()

const screenshot = '![截图](screenshot://aabbccdd-1122-3344-5566-aabbccddeeff)'
const render = (slots, attrs = {}) => renderToString(createSSRApp({
  render: () => h(ScreenshotDescriptions, { column: 2, border: true, size: 'small', ...attrs }, slots),
}))

test('详情保留静态、v-for、条件字段及原生子项布局', async () => {
  for (const visible of [true, false]) {
    const html = await render({ default: () => [
      h(ElDescriptionsItem, { label: '订单号' }, { default: () => 'TEST-001' }),
      h(ElDescriptionsItem, { label: '项目名称' }, { default: () => createTextVNode('测试项目') }),
      h(Fragment, null, ['客户全称', '客户简称'].map(label => h(ElDescriptionsItem, { key: label, label }, { default: () => `${label}内容` }))),
      visible ? h(ElDescriptionsItem, { label: '备注', span: 2, className: 'detail-note', labelClassName: 'detail-label' }, { default: () => '多行备注\n第二行' }) : createCommentVNode('v-if'),
    ] })
    for (const value of ['订单号', 'TEST-001', '项目名称', '测试项目', '客户全称内容', '客户简称内容']) assert.ok(html.includes(value), value)
    assert.equal(html.includes('第二行'), visible)
    if (visible) {
      assert.match(html, /colspan="3"/)
      assert.match(html, /detail-note/)
      assert.match(html, /detail-label/)
    }
    assert.match(html, /el-descriptions--small/)
    assert.match(html, /is-bordered/)
  }
})

test('透传标题、额外插槽、自定义标签及字段交互组件', async () => {
  const html = await render({
    title: () => h('strong', '客户详情'),
    extra: () => h('button', '更多'),
    default: () => h(ElDescriptionsItem, { label: '原标签', align: 'right', labelWidth: 123 }, {
      label: () => h('b', '自定义标签'),
      default: () => h('button', { 'aria-label': '编辑备注', onClick: () => {} }, '编辑内容'),
    }),
  }, { class: 'custom-detail', 'data-detail': 'customer' })
  for (const text of ['custom-detail', 'data-detail="customer"', '<strong>客户详情</strong>', '更多', '<b>自定义标签</b>', 'aria-label="编辑备注"', '编辑内容', 'is-right', '123px']) assert.ok(html.includes(text), text)
  assert.ok(!html.includes('原标签'))
})

test('截图转换支持原始文本、文本节点、嵌套元素及组件插槽', async () => {
  const Nested = { setup: (_, { slots }) => () => h('section', slots.default?.()) }
  const html = await render({ default: () => [
    h(ElDescriptionsItem, { label: '字符串' }, { default: () => screenshot }),
    h(ElDescriptionsItem, { label: '文本节点' }, { default: () => createTextVNode(screenshot) }),
    h(ElDescriptionsItem, { label: '嵌套元素' }, { default: () => h('div', screenshot) }),
    h(ElDescriptionsItem, { label: '组件插槽' }, { default: () => h(Nested, null, { default: () => h('p', screenshot) }) }),
  ] })
  assert.equal((html.match(/screenshot-test-preview/g) || []).length, 4)
  assert.match(html, /<section><p>/)
})

test('缺失插槽、空字段与空内容正常渲染', async () => {
  for (const slots of [{}, { default: () => null }, { default: () => [] }]) assert.match(await render(slots), /<tbody>/)
  const html = await render({ default: () => h(ElDescriptionsItem, { label: '空字段' }, { default: () => null }) })
  assert.match(html, /空字段/)
  assert.ok(!html.includes('undefined'))
})

test('表格截图仍支持属性取值、格式化器及自定义插槽', () => {
  const row = { nested: { note: screenshot } }
  const scope = { row, column: {}, $index: 0 }
  const column = (attrs, slots = {}) => ScreenshotTableColumn.setup({}, { attrs, slots })()
  assert.equal(column({ prop: 'nested.note' }).children.default(scope).props.text, screenshot)
  assert.equal(column({ prop: 'nested.note', formatter: () => '普通内容' }).children.default(scope), '普通内容')
  assert.equal(column({}, { default: () => h('span', screenshot) }).children.default(scope)[0].children[0].props.text, screenshot)
})

test('全局自动解析包装父级并保留原生详情项', () => {
  const config = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8')
  assert.match(config, /ElDescriptions:'ScreenshotDescriptions'/)
  assert.ok(!config.includes('ScreenshotDescriptionsItem'))
})
