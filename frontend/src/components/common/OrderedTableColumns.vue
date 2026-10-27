<script>
import { computed, defineComponent } from 'vue'
import { useTableColumnOrder } from '@/composables/useTableColumnOrder'
import { useTableHeaderOrder } from '@/composables/useTableHeaderOrder'
import { orderTableColumnNodes } from '@/utils/orderTableColumnNodes'

// Render a fragment inside ElTable: keep its native ref, selection, expansion and cell slots.
export default defineComponent({
  props: { settingsKey: { type: String, required: true }, section: { type: String, default: 'main' } },
  setup(props, { slots }) {
    const state = useTableColumnOrder(computed(() => props.settingsKey), computed(() => props.section))
    const { order, custom, columns } = state
    useTableHeaderOrder(state)
    return () => {
      const nodes = slots.default?.() || []
      if (!custom.value) return nodes
      return orderTableColumnNodes(nodes, columns.value, order.value)
    }
  },
})
</script>

<style>
.el-table th.column-order-draggable { cursor: grab; }
.el-table th.column-order-draggable:active { cursor: grabbing; }
.el-table th.column-order-drop-target { box-shadow: inset 3px 0 var(--el-color-primary); background: var(--el-color-primary-light-9) !important; }
.column-order-dragging, .column-order-dragging * { user-select: none !important; cursor: grabbing !important; }
</style>
