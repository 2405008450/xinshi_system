export const COLUMN_RESIZE_HIT_WIDTH = 14
export function resizedColumnWidth(width, delta, scale = 1, minimum = 40) {
  return Math.max(minimum, Math.round(width + delta / (scale > 0 ? scale : 1)))
}

// Capture phase gives resizing priority over column ordering and native mouse handlers.
// getColumns returns current header elements; refreshed after visibility/order changes.
export function bindColumnResize(root, getColumns, commit) {
  const doc = root.ownerDocument, win = doc.defaultView
  const handles = new Map()
  let observer, active, guide, clickBlocked = false, disposed = false, queued = false, columns = []
  function refresh() {
    queued = false
    if (disposed || active) return
    columns = getColumns()
    const live = new Set()
    for (const column of columns) {
      const el = column.element
      if (!el || el.getBoundingClientRect().width < 3) continue
      live.add(el)
      let handle = handles.get(el)
      if (!handle) {
        handle = doc.createElement('span')
        handle.className = 'app-column-resize-handle'
        handle.setAttribute('role', 'separator'); handle.setAttribute('aria-orientation', 'vertical')
        handle.setAttribute('tabindex', '0'); handle.title = '左右拖动调整列宽；方向键微调，Shift 加速'
        el.classList.add('app-column-resize-header'); el.appendChild(handle); handles.set(el, handle)
      }
      handle.columnResize = column
      handle.setAttribute('aria-label', `调整${column.label || '此列'}宽度`)
      handle.setAttribute('aria-valuenow', String(Math.round(column.width)))
    }
    for (const [el, handle] of handles) if (!live.has(el)) { handle.remove(); el.classList.remove('app-column-resize-header'); handles.delete(el) }
  }
  function schedule() { if (!queued && !disposed) { queued = true; queueMicrotask(refresh) } }
  function nearBodyBorder(event) {
    if (!event.target.closest?.('td') || event.target.closest('input,textarea,select,button,a,[role=button]')) return null
    const ownerTable = event.target.closest('.el-table')
    if (ownerTable && ownerTable !== root) return null
    const bounds = root.getBoundingClientRect()
    let nearest = null, distance = COLUMN_RESIZE_HIT_WIDTH / 2 + 1
    for (const column of columns) {
      // Grouped headers share a boundary with their leaf; prefer the leaf.
      if (column.leaf && column.leaf !== column.element) continue
      const rect = column.element.getBoundingClientRect(), diff = Math.abs(rect.right - event.clientX)
      if (rect.width > 2 && rect.right >= bounds.left && rect.right <= bounds.right + 1 && diff < distance) { nearest = column; distance = diff }
    }
    return nearest
  }
  function hover(event) {
    if (active) return
    const column = nearBodyBorder(event)
    if (column) root.classList.add('app-column-resize-hover')
    else root.classList.remove('app-column-resize-hover')
  }
  function leave() { if (!active) root.classList.remove('app-column-resize-hover') }
  function down(event) {
    const handle = event.target.closest?.('.app-column-resize-handle')
    if (event.button !== 0 || (handle && !root.contains(handle))) return
    const column = handle?.columnResize || nearBodyBorder(event)
    if (!column) return
    event.preventDefault(); event.stopImmediatePropagation()
    const rect = column.element.getBoundingClientRect()
    const leafRect = (column.leaf || column.element).getBoundingClientRect()
    active = { column, x: event.clientX, width: column.width, scale: leafRect.width / column.width, right: rect.right, end: event.clientX, pointerId: event.pointerId }
    guide = doc.createElement('div'); guide.className = 'app-column-resize-guide'
    const tableRect = root.getBoundingClientRect()
    Object.assign(guide.style, { left: `${rect.right}px`, top: `${rect.top}px`, height: `${Math.max(rect.height, tableRect.bottom - rect.top)}px` })
    doc.body.appendChild(guide); doc.documentElement.classList.add('app-column-resizing')
    ;(handle || root).setPointerCapture?.(event.pointerId)
  }
  function move(event) {
    if (!active || event.pointerId !== active.pointerId) return
    event.preventDefault()
    active.end = event.clientX
    const width = resizedColumnWidth(active.width, active.end - active.x, active.scale, active.column.minimum)
    guide.style.left = `${active.right + (width - active.width) * active.scale}px`
  }
  function cleanup() {
    active = null; guide?.remove(); guide = null; doc.documentElement.classList.remove('app-column-resizing'); root.classList.remove('app-column-resize-hover'); schedule()
  }
  function up(event) {
    if (!active || event.pointerId !== active.pointerId) return
    const { column, width, x, scale } = active
    commit(column, resizedColumnWidth(width, event.clientX - x, scale, column.minimum), width, event)
    clickBlocked = true; win.setTimeout(() => { clickBlocked = false }, 0)
    cleanup()
  }
  function cancel(event) { if (!event || !active || event.pointerId === active.pointerId) cleanup() }
  function click(event) { if (clickBlocked) { event.preventDefault(); event.stopImmediatePropagation() } }
  function key(event) {
    const handle = event.target.closest?.('.app-column-resize-handle')
    if (!handle || !root.contains(handle) || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return
    event.preventDefault(); event.stopImmediatePropagation()
    const column = handle.columnResize, delta = (event.key === 'ArrowLeft' ? -1 : 1) * (event.shiftKey ? 40 : 8)
    commit(column, resizedColumnWidth(column.width, delta, 1, column.minimum), column.width, event); schedule()
  }
  root.addEventListener('pointerdown', down, true); root.addEventListener('keydown', key, true); root.addEventListener('click', click, true)
  root.addEventListener('pointermove', hover, true); root.addEventListener('pointerleave', leave)
  doc.addEventListener('pointermove', move, { passive: false }); doc.addEventListener('pointerup', up); doc.addEventListener('pointercancel', cancel)
  win.addEventListener('blur', cleanup)
  observer = new MutationObserver(schedule); observer.observe(root, { childList: true, subtree: true })
  refresh()
  return () => {
    disposed = true; observer.disconnect(); cleanup()
    root.removeEventListener('pointerdown', down, true); root.removeEventListener('keydown', key, true); root.removeEventListener('click', click, true)
    root.removeEventListener('pointermove', hover, true); root.removeEventListener('pointerleave', leave)
    doc.removeEventListener('pointermove', move); doc.removeEventListener('pointerup', up); doc.removeEventListener('pointercancel', cancel); win.removeEventListener('blur', cleanup)
    for (const [el, handle] of handles) { handle.remove(); el.classList.remove('app-column-resize-header') }
    handles.clear()
  }
}

export function installTableColumnResize(app) {
  const cleanups = new WeakMap()
  app.mixin({
    mounted() {
      if (this.$options.name !== 'ElTable') return
      const instance = this.$, root = this.$el, widths = new Map(), restored = new Set()
      const find = (columns, id) => {
        for (const column of columns) { if (column.id === id) return column; const child = column.children && find(column.children, id); if (child) return child }
      }
      const key = column => column.columnKey || column.property || column.label || column.id
      cleanups.set(instance, bindColumnResize(root, () => [...root.querySelectorAll('thead th')].filter(el => el.closest('.el-table') === root).flatMap(element => {
        const id = [...element.classList].find(value => /^el-table_.*_column_/.test(value))
        let column = find(instance.store.states._columns.value, id)
        if (!column) return []
        // A grouped header's right edge resizes its rightmost leaf.
        while (column.children?.length) column = column.children.at(-1)
        const leaf = root.querySelector(`thead th.${column.id}`)
        if (!leaf) return []
        if (!restored.has(column.id)) {
          restored.add(column.id)
          if (widths.has(key(column))) { column.width = column.realWidth = widths.get(key(column)); instance.store.scheduleLayout(false, true) }
        }
        return [{ element, column, width: Number(column.realWidth || column.width) || leaf.offsetWidth, minimum: ['selection', 'index', 'expand'].includes(column.type) ? 32 : 40, label: column.label, leaf }]
      }), (entry, width, previous, event) => {
        entry.column.width = entry.column.realWidth = width; widths.set(key(entry.column), width)
        instance.emit('header-dragend', width, previous, entry.column, event); instance.store.scheduleLayout(false, true)
      }))
    },
    beforeUnmount() { cleanups.get(this.$)?.(); cleanups.delete(this.$) },
  })
}

export function bindPlainTableColumnResize(header) {
  const table = header.closest('table'), doc = header.ownerDocument, widths = new Map()
  let colgroup
  function apply(headers) {
    if (!colgroup) { colgroup = doc.createElement('colgroup'); table.prepend(colgroup) }
    while (colgroup.children.length < headers.length) colgroup.appendChild(doc.createElement('col'))
    while (colgroup.children.length > headers.length) colgroup.lastElementChild.remove()
    let total = 0
    headers.forEach((element, index) => {
      const key = element.dataset.columnKey || `structure:${index}:${element.textContent.trim()}`
      if (!widths.has(key)) widths.set(key, element.offsetWidth)
      const width = widths.get(key); total += width
      colgroup.children[index].style.width = `${width}px`
      Object.assign(element.style, { width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` })
    })
    Object.assign(table.style, { tableLayout: 'fixed', width: `${total}px`, minWidth: '0' })
  }
  return bindColumnResize(table, () => {
    const headers = [...header.querySelectorAll('tr:first-child > th')]
    apply(headers)
    return headers.map((element, index) => ({ element, key: element.dataset.columnKey || `structure:${index}:${element.textContent.trim()}`, width: element.offsetWidth, minimum: 40, label: element.textContent.trim() }))
  }, (entry, width) => { widths.set(entry.key, width); apply([...header.querySelectorAll('tr:first-child > th')]) })
}
