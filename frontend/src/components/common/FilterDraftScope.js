import { cloneVNode, defineComponent, h, isVNode, reactive } from 'vue'
import { emptyFilterValue } from '@/utils/listFieldFilters'

const copy = value => value == null ? value : JSON.parse(JSON.stringify(value))
const call = (handler, ...args) => {
  for (const fn of Array.isArray(handler) ? handler : [handler]) if (typeof fn === 'function') fn(...args)
}
const empty = props => {
  if (props.definition) return emptyFilterValue(props.definition)
  if (Array.isArray(props.modelValue) || props.multiple || /range/.test(props.type || '')) return []
  if (typeof props.modelValue === 'boolean') return false
  if (typeof props.modelValue === 'number') return undefined
  return ''
}

// 只管理筛选浮层的输入副本；正式条件始终由业务页面持有。
// 关闭只隐藏浮层，输入副本保留到确认、清除或正式条件发生变化。
export default defineComponent({
  name: 'FilterDraftScope',
  emits: ['apply', 'cancel'],
  setup(props, { slots, expose, emit }) {
    const values = reactive(new Map())
    const bindings = new Map()
    let pendingQuery
    const discard = () => { values.clear(); bindings.clear(); pendingQuery = undefined }
    function bind(key, appliedValue, binding) {
      const applied = JSON.stringify(appliedValue)
      if (!bindings.has(key) || bindings.get(key).applied !== applied) {
        values.set(key, copy(appliedValue))
      }
      bindings.set(key, { ...binding, applied })
    }
    function apply() {
      for (const [key, binding] of bindings) {
        const value = values.get(key)
        if (JSON.stringify(value) !== binding.applied) binding.write(copy(value))
      }
      const query = pendingQuery || [...bindings.values()].find(binding => binding.query)?.query
      pendingQuery = undefined
      query?.()
      emit('apply')
    }
    function cancel() {
      for (const [key, binding] of bindings) values.set(key, copy(binding.empty))
      apply()
      emit('cancel')
    }
    expose({ apply, discard, cancel })
    function transform(nodes, path = '') {
      return (Array.isArray(nodes) ? nodes : [nodes]).map((node, index) => {
        if (!isVNode(node)) return node
        const key = path + '/' + (node.key ?? index)
        const next = cloneVNode(node)
        const original = node.props || {}
        next.props = { ...original }
        if (typeof original['onUpdate:modelValue'] === 'function' || Array.isArray(original['onUpdate:modelValue'])) {
          bind(key, original.modelValue, { write: value => call(original['onUpdate:modelValue'], value),
            empty: empty(original),
            query: () => call(original.onEnter || original.onChange || original.onTextInput || original.onInput, values.get(key)) })
          next.props.modelValue = values.get(key)
          next.props['onUpdate:modelValue'] = value => { values.set(key, copy(value)) }
          for (const event of ['onInput', 'onChange', 'onClear', 'onTextInput', 'onEnter']) {
            if (original[event]) next.props[event] = (...args) => { pendingQuery = () => call(original[event], ...args) }
          }
          if (original.onKeyup) next.props.onKeyup = event => {
            if (event.key === 'Enter') { apply(); call(original.onKeyup, event) }
          }
        } else if (original.model && Array.isArray(original.fields) && original.onUpdate) {
          const fields = original.fields
          const model = {}
          for (const field of fields) {
            const fieldKey = key + ':' + field.key
            bind(fieldKey, original.model[field.key] ?? emptyFilterValue(field), { write: value => call(original.onUpdate, field.key, value),
              empty: emptyFilterValue(field),
              query: () => call(original.onEnter || original.onChange, field, values.get(fieldKey)) })
            model[field.key] = values.get(fieldKey)
          }
          next.props.model = model
          next.props.onUpdate = (field, value) => values.set(key + ':' + field, copy(value))
          for (const event of ['onTextInput', 'onChange', 'onEnter']) {
            if (original[event]) next.props[event] = (...args) => { pendingQuery = () => call(original[event], ...args) }
          }
        }
        if (Array.isArray(node.children)) next.children = transform(node.children, key)
        else if (node.children && typeof node.children === 'object') {
          next.children = Object.fromEntries(Object.entries(node.children).map(([name, slot]) => [
            name, typeof slot === 'function' ? (...args) => transform(slot(...args), key + ':' + name) : slot,
          ]))
          // 新插槽函数依赖本地副本，不能继承编译器的稳定插槽标记。
          next.children._ = 2
          next.patchFlag = 0
          next.dynamicChildren = null
        }
        next.patchFlag = 0
        next.dynamicChildren = null
        return next
      })
    }
    return () => h('div', {
      class: 'filter-draft-scope', 'data-auto-draft': 'off',
      onClickCapture: event => {
        const button = event.target.closest('button')
        if (!button) return
        const text = button.textContent.trim()
        if (/^(确定|确认|应用|查询|确认选择)$/.test(text)) apply()
        else if (/取消筛选|清除.*筛选|清空.*条件|重置|恢复默认/.test(text)) discard()
      },
    }, transform(slots.default?.() || []))
  },
})
