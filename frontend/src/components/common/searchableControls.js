import { cloneVNode, defineComponent, Fragment, h, ref } from 'vue'
import { ElSelect, ElCascader, ElTransfer } from 'element-plus'
import { matchesSearch } from '../../utils/searchMatching.js'

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
function searchableControl(name, component, defaults) {
  return defineComponent({
    name, inheritAttrs: false,
    setup(_, { attrs, slots, expose }) {
      const control = ref(), keyword = ref('')
      expose(new Proxy({}, { get: (_, key) => {
        const value = control.value?.[key]
        return typeof value === 'function' ? value.bind(control.value) : value
      }, has: (_, key) => key in (control.value || {}) }))
      return () => {
        const remote = attrs.remote !== undefined && attrs.remote !== false
        const local = attrs.filterable !== undefined && attrs.filterable !== false && !remote && !attrs.filterMethod && !attrs['filter-method']
        const extra = local ? defaults(attrs, keyword) : {}
        const content = local && component === ElSelect && slots.default
          ? { ...slots, default: () => filterSearchOptions(slots.default(), keyword.value) } : slots
        return h(component, { ...attrs, ...extra, ref: control }, content)
      }
    },
  })
}
export const SearchSelect = searchableControl('SearchSelect', ElSelect, (_, keyword) => ({ filterMethod: value => { keyword.value = value } }))
export const SearchCascader = searchableControl('SearchCascader', ElCascader, () => ({ filterMethod: (node, keyword) => matchesSearch(node.text || node.label, keyword) }))
export const SearchTransfer = searchableControl('SearchTransfer', ElTransfer, attrs => ({ filterMethod: (keyword, item) => matchesSearch(item[attrs.props?.label || 'label'], keyword) }))
