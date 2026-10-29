// Pointer gestures also work in embedded browsers, which may omit HTML drag/drop events.
export function bindColumnDrag(root, resolve, move, highlight = () => {}) {
  const document = root.ownerDocument
  let start = null, active = false, suppressClick = false
  function down(event) {
    if (event.button !== 0 || event.defaultPrevented || event.target.closest?.('.app-column-resize-handle')) return
    const value = resolve(event.target, false, event)
    if (value == null) return
    start = { value, x: event.clientX, y: event.clientY }
    active = false
    event.preventDefault()
  }
  function pointerMove(event) {
    if (!start) return
    if (!active && Math.hypot(event.clientX - start.x, event.clientY - start.y) < 6) return
    active = true
    root.classList.add('column-order-dragging')
    highlight(resolve(document.elementFromPoint(event.clientX, event.clientY)))
    event.preventDefault()
  }
  function finish(event) {
    if (start && active) {
      const target = resolve(document.elementFromPoint(event.clientX, event.clientY))
      if (target != null) move(start.value, target)
      suppressClick = true
      setTimeout(() => { suppressClick = false }, 0)
    }
    cancel()
  }
  function cancel() { start = null; active = false; root.classList.remove('column-order-dragging'); highlight(null) }
  function click(event) { if (suppressClick) { suppressClick = false; event.stopImmediatePropagation(); event.preventDefault() } }
  root.addEventListener('pointerdown', down)
  root.addEventListener('click', click, true)
  document.addEventListener('pointermove', pointerMove, { passive: false })
  document.addEventListener('pointerup', finish)
  document.addEventListener('pointercancel', cancel)
  return () => {
    cancel()
    root.removeEventListener('pointerdown', down)
    root.removeEventListener('click', click, true)
    document.removeEventListener('pointermove', pointerMove)
    document.removeEventListener('pointerup', finish)
    document.removeEventListener('pointercancel', cancel)
  }
}
