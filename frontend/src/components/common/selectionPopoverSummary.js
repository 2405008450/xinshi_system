import { defineComponent, h } from 'vue'
import MultiSelectSummary from './multiSelectSummary.js'

// 单独订阅选择集合，避免浮窗的默认插槽在子控件注册时重复创建自身内容。
export default defineComponent({
  name: 'SelectionPopoverSummary',
  props: { groups: { type: Map, required: true } },
  emits: ['confirm'],
  setup(props, { emit }) {
    return () => props.groups.size ? h(MultiSelectSummary, {
      labels: [...props.groups.values()].flatMap(group => group.labels.value),
      optionCount: [...props.groups.values()].reduce((count, group) => count + group.optionCount.value, 0),
      onConfirm: () => emit('confirm'),
    }) : null
  },
})
