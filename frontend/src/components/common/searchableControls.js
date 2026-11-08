import { cloneVNode, defineComponent, Fragment, h, ref } from 'vue'
import { ElSelect, ElSelectV2, ElCascader, ElTransfer } from 'element-plus'
import { matchesSearch } from '../../utils/searchMatching.js'
import MultiSelectSummary from './multiSelectSummary.js'

// 仅替换本地控件的默认搜索；远程查询和业务自定义过滤继续由调用方负责。
export function filterSearchOptions(nodes, keyword) {
  return (nodes || []).flatMap(node => {
    if (!node || typeof node !== 'object') return [node]
    if (node.type?.name === 'ElOption') return matchesSearch(node.props?.label ?? node.props?.value, keyword) ? [node] : []
    if (node.type === Fragment) return [cloneVNodeWithChildren(node, filterSearchOptions(node.children, keyword))]
    if (node.type?.name === 'ElOptionGroup' && node.children?.default) {
      const children = filterSearchOptions(node.children.default(), keyword)
      return children.length ? [cloneVNodeWithChildren(node, { ...node.children, default: () => children })] : []
    }
    return [node]
  })
}
function cloneVNodeWithChildren(node, children) {
  const cloned = cloneVNode(node)
  cloned.children = children
  // v-for 的稳定块不能保留旧的 dynamicChildren，否则过滤后会复用错误选项。
  cloned.dynamicChildren = null
  cloned.patchFlag = 0
  return cloned
}
function optionKey(value, valueKey = 'value') {
  return value && typeof value === 'object' ? value[valueKey] : value
}
function collectOptionLabels(nodes, cache, valueKey) {
  for (const node of nodes || []) {
    if (node?.type?.name === 'ElOption') cache.set(optionKey(node.props?.value, valueKey), node.props?.label ?? node.props?.value)
    else if (Array.isArray(node?.children)) collectOptionLabels(node.children, cache, valueKey)
    else if (node?.type?.name === 'ElOptionGroup') collectOptionLabels(node.children?.default?.(), cache, valueKey)
  }
}
function collectDataLabels(options, cache, props = {}, path = [], cascader = false) {
  for (const option of options || []) {
    const value = option[props.value || 'value'], label = option[props.label || 'label'] ?? value
    const labels = [...path, label]
    if (value !== undefined) cache.set(value, cascader ? labels.join(' / ') : label)
    collectDataLabels(option[props.children || (cascader ? 'children' : 'options')], cache, props, labels, cascader)
  }
}
export function countDataOptions(options, props = {}, cascader = false) {
  return (options || []).reduce((count, option) => {
    const children = option[props.children || (cascader ? 'children' : 'options')]
    const hasValue = option[props.value || 'value'] !== undefined
    const selectable = hasValue && (!children?.length || cascader && props.checkStrictly)
    return count + (selectable ? 1 : 0) + countDataOptions(children, props, cascader)
  }, 0)
}
function searchableControl(name, component, defaults) {
  return defineComponent({
    name, inheritAttrs: false,
    setup(_, { attrs, slots, expose }) {
      const control = ref(), keyword = ref(''), selectedLabels = new Map()
      const confirm = () => {
        if (component === ElCascader) control.value?.togglePopperVisible(false)
        else if (control.value) control.value.expanded = false
      }
      expose(new Proxy({}, { get: (_, key) => {
        const value = control.value?.[key]
        return typeof value === 'function' ? value.bind(control.value) : value
      }, has: (_, key) => key in (control.value || {}) }))
      return () => {
        const remote = attrs.remote !== undefined && attrs.remote !== false
        const local = attrs.filterable !== undefined && attrs.filterable !== false && !remote && !attrs.filterMethod && !attrs['filter-method']
        const extra = local ? defaults(attrs, keyword) : {}
        // 多选后清空搜索词；显式配置保留行为时仍以业务调用方为准。
        const selectionDefaults = component === ElSelect && !('reserveKeyword' in attrs) && !('reserve-keyword' in attrs)
          ? { reserveKeyword: false } : {}
        // ElSelect 的选项收集 watcher 也会调用默认插槽；先在本组件渲染时
        // 求值，避免 watcher 在渲染之外执行父组件插槽而丢失依赖跟踪。
        let content = slots, optionCount = 0
        if (component === ElSelect && slots.default) {
          const nodes = slots.default()
          const catalog = new Map()
          collectOptionLabels(nodes, catalog, attrs.valueKey || attrs['value-key'])
          catalog.forEach((label, value) => selectedLabels.set(value, label))
          optionCount = remote ? selectedLabels.size : catalog.size
          const options = local ? filterSearchOptions(nodes, keyword.value) : nodes
          content = { ...slots, default: () => options }
        }
        const multiple = component === ElCascader ? attrs.props?.multiple === true : attrs.multiple !== undefined && attrs.multiple !== false
        if (multiple && component !== ElTransfer) {
          if (component !== ElSelect) {
            collectDataLabels(attrs.options, selectedLabels, attrs.props, [], component === ElCascader)
            optionCount = remote ? selectedLabels.size : countDataOptions(attrs.options, attrs.props, component === ElCascader)
          }
          const values = attrs.modelValue || attrs['model-value'] || []
          const labels = values.map(value => {
            const key = component === ElCascader && Array.isArray(value) ? value.at(-1) : optionKey(value, attrs.valueKey || attrs['value-key'])
            return selectedLabels.get(key) ?? String(key ?? '')
          })
          content = { ...content, footer: () => {
            // 独立缓存选项标签，不依赖搜索结果，也不在子控件插槽中读取其状态造成循环更新。
            return [slots.footer?.(), h(MultiSelectSummary, { labels, optionCount, onConfirm: confirm })]
          } }
        }
        return h(component, { ...selectionDefaults, ...attrs, ...extra, ref: control }, content)
      }
    },
  })
}
export const SearchSelect = searchableControl('SearchSelect', ElSelect, (_, keyword) => ({ filterMethod: value => { keyword.value = value } }))
export const SearchSelectV2 = searchableControl('SearchSelectV2', ElSelectV2, () => ({}))
export const SearchCascader = searchableControl('SearchCascader', ElCascader, () => ({ filterMethod: (node, keyword) => matchesSearch(node.text || node.label, keyword) }))
export const SearchTransfer = searchableControl('SearchTransfer', ElTransfer, attrs => ({ filterMethod: (keyword, item) => matchesSearch(item[attrs.props?.label || 'label'], keyword) }))
