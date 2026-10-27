import { getCurrentInstance, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { moveColumn } from '../utils/tableColumnOrder'
import { bindColumnDrag } from '../utils/columnDragGesture'

export function useTableHeaderOrder(state) {
  let owner = getCurrentInstance()?.parent
  while (owner && !owner.tableId) owner = owner.parent
  let root, observer, unbindDrag
  const tagged = new Set()
  const findField = column => state.columns.value.find(field => [column.property, column.columnKey].includes(field.key))
    || state.columns.value.find(field => field.label === column.label)
  function refresh() {
    const nativeColumns = owner?.store?.states?._columns?.value || []
    function find(columns, id) {
      for (const column of columns) {
        if (column.id === id) return column
        const child = column.children && find(column.children, id)
        if (child) return child
      }
    }
    root?.querySelectorAll('thead th').forEach(th => {
      if (th.closest('.el-table') !== root) return
      const column = find(nativeColumns, [...th.classList].find(name => /^el-table_.*_column_/.test(name)))
      const field = column && findField(column)
      if (field && !column.type?.match(/selection|index|expand/)) {
        th.draggable = false
        th.dataset.columnOrderKey = String(field.key)
        th.classList.add('column-order-draggable')
        th.title = '拖动表头调整字段顺序'
        tagged.add(th)
      }
    })
  }
  function resolve(element, moving = true, event) {
    if (element?.closest('button,input,textarea,select,a,[role=button],.el-checkbox')) return null
    const th = element?.closest('th[data-column-order-key]')
    if (!moving && th && th.getBoundingClientRect().right - event.clientX < 8) return null
    return th?.closest('.el-table') === root ? th.dataset.columnOrderKey : null
  }
  onMounted(async () => {
    await nextTick()
    root = owner?.vnode.el
    if (!root) return
    unbindDrag = bindColumnDrag(root, resolve, (from, to) => {
      const keys = state.order.value
      state.setOrder(moveColumn(keys, keys.find(key => String(key) === from), keys.find(key => String(key) === to)))
    }, key => root.querySelectorAll('th[data-column-order-key]').forEach(th => th.classList.toggle('column-order-drop-target', th.dataset.columnOrderKey === key)))
    observer = new MutationObserver(refresh)
    const header = root.querySelector('.el-table__header-wrapper')
    if (header) observer.observe(header, { childList: true, subtree: true })
    refresh()
  })
  watch([state.order, state.columns], () => nextTick(refresh), { deep: true })
  onBeforeUnmount(() => {
    observer?.disconnect()
    unbindDrag?.()
    tagged.forEach(th => { th.removeAttribute('draggable'); delete th.dataset.columnOrderKey; th.classList.remove('column-order-draggable') })
  })
}
