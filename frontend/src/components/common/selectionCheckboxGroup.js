import { computed, defineComponent, h, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElCheckboxGroup } from 'element-plus'
import { multiSelectionContext } from './multiSelectionContext.js'

function labelText(nodes) {
  return (Array.isArray(nodes) ? nodes : [nodes]).map(node => {
    if (typeof node === 'string' || typeof node === 'number') return String(node)
    if (Array.isArray(node?.children)) return labelText(node.children)
    return typeof node?.children === 'string' ? node.children : ''
  }).join('').trim()
}

export const SelectionCheckboxGroup = defineComponent({
  name: 'SelectionCheckboxGroup', inheritAttrs: false,
  setup(_, { attrs, slots, expose }) {
    const context = inject(multiSelectionContext, null), cache = new Map(), control = ref(), key = Symbol()
    const labels = computed(() => (attrs.modelValue || attrs['model-value'] || []).map(value => cache.get(value) || String(value)))
    const optionCount = ref(0)
    onMounted(() => context?.set(key, { labels, optionCount }))
    onBeforeUnmount(() => context?.delete(key))
    expose(new Proxy({}, { get: (_, name) => control.value?.[name] }))
    function collect(nodes) {
      for (const node of nodes || []) {
        if (node?.type?.name === 'ElCheckbox') {
          const value = node.props?.value ?? node.props?.label
          if (value !== undefined) cache.set(value, labelText(node.children?.default?.() || node.props?.label || value))
        } else if (Array.isArray(node?.children)) collect(node.children)
      }
    }
    return () => {
      const nodes = slots.default?.() || []
      if (context) collect(nodes)
      if (context) optionCount.value = cache.size
      return h(ElCheckboxGroup, { ...attrs, ref: control }, { ...slots, default: () => nodes })
    }
  },
})
