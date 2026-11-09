// All geometry uses viewport pixels; only header translation is converted back
// to local CSS pixels, so application zoom and teleported dialogs behave alike.
export function tableScrollGeometry({ root, header, source, clip, scale = 1, offset = 0, trackHeight = 14 }) {
  const top = Math.max(0, clip.top), bottom = Math.min(clip.bottom, root.bottom)
  const origin = header ? header.top - offset * scale : root.top
  const shift = header ? Math.max(0, Math.min(top - origin, root.bottom - header.height - origin)) / scale : 0
  const left = Math.max(source.left, clip.left), right = Math.min(source.right, clip.right)
  const barBottom = Math.min(source.bottom, bottom)
  return { shift, left, width: Math.max(0, right - left), top: barBottom - trackHeight,
    visible: right > left && barBottom - trackHeight >= Math.max(top, source.top, header ? origin + shift * scale + header.height : root.top) }
}

export function horizontalThumb(viewport, content, value, track) {
  const maximum = Math.max(0, content - viewport)
  const width = Math.min(track, Math.max(32, track * viewport / Math.max(1, content)))
  return { maximum, width, left: maximum ? Math.max(0, Math.min(maximum, value)) / maximum * (track - width) : 0 }
}

export function installTableScrollVisibility(doc = document) {
  const win = doc.defaultView, entries = new Map()
  let frame = 0, stopped = false
  const css = (element, key, value) => { if (element.style[key] !== value) element.style[key] = value }
  const schedule = () => { if (!frame && !stopped) frame = win.requestAnimationFrame(refresh) }
  const own = (root, selector) => [...root.querySelectorAll(selector)].find(el => el.closest('.el-table') === root)
  const overflow = value => /auto|scroll|hidden|clip/.test(value)
  let scaleCache = new WeakMap()
  function scaleOf(element) {
    if (!element || element === doc.documentElement) return { x: 1, y: 1 }
    if (scaleCache.has(element)) return scaleCache.get(element)
    const parent = scaleOf(element.parentElement), style = win.getComputedStyle(element), zoom = Number.parseFloat(style.zoom) || 1
    const matrix = style.transform === 'none' ? null : new win.DOMMatrixReadOnly(style.transform)
    const scale = { x: parent.x * zoom * (matrix ? Math.hypot(matrix.a, matrix.b) : 1), y: parent.y * zoom * (matrix ? Math.hypot(matrix.c, matrix.d) : 1) }
    scaleCache.set(element, scale)
    return scale
  }
  function horizontalSource(root) {
    for (let el = root.parentElement; el && el !== doc.body; el = el.parentElement) {
      if (overflow(win.getComputedStyle(el).overflowX)) return el
    }
    return doc.scrollingElement
  }
  function descriptor(root) {
    if (root.matches('.el-table')) return { root, header: own(root, '.el-table__header-wrapper'), source: own(root, '.el-table__body-wrapper .el-scrollbar__wrap') }
    if (root.matches('table')) {
      if (root.matches('.el-table__header,.el-table__body,.el-table__footer')) return null
      return { root, header: root.tHead, source: horizontalSource(root) }
    }
    return { root, header: root.querySelector('.project-summary--header'), source: root }
  }
  function clipping(element) {
    let bounds = { left: 0, top: 0, right: win.innerWidth, bottom: win.innerHeight }, z = 20
    // Include the source's own viewport: important for a plain table's internal
    // vertical scroller and for the scrollbar above a dialog's fixed footer.
    for (let el = element; el && el !== doc.body; el = el.parentElement) {
      const style = win.getComputedStyle(el), rect = el.getBoundingClientRect()
      const { x: sx, y: sy } = scaleOf(el)
      if (overflow(style.overflowX)) { bounds.left = Math.max(bounds.left, rect.left + el.clientLeft * sx); bounds.right = Math.min(bounds.right, rect.left + (el.clientLeft + el.clientWidth) * sx) }
      if (overflow(style.overflowY)) { bounds.top = Math.max(bounds.top, rect.top + el.clientTop * sy); bounds.bottom = Math.min(bounds.bottom, rect.top + (el.clientTop + el.clientHeight) * sy) }
      z = Math.max(z, (Number.parseInt(style.zIndex, 10) || 0) + 2)
    }
    return { ...bounds, z }
  }
  function bind(item) {
    const { root, header, source } = item
    const track = doc.createElement('div'), thumb = doc.createElement('div')
    track.className = 'app-table-horizontal-scroll'; thumb.className = 'app-table-horizontal-thumb'
    track.tabIndex = 0; track.setAttribute('role', 'scrollbar'); track.setAttribute('aria-label', '表格水平滚动条')
    track.setAttribute('aria-orientation', 'horizontal'); track.setAttribute('aria-valuemin', '0')
    if (!source.id) { source.id = `app-table-scroll-${++sequence}`; item.generatedId = true }
    track.setAttribute('aria-controls', source.id)
    track.append(thumb); doc.body.append(track)
    item.track = track; item.thumb = thumb; item.offset = 0
    item.headerTransform = header?.style.transform || ''
    item.paddingTarget = root.matches('.el-table') ? own(root, '.el-table__body-wrapper .el-scrollbar__view') || source : source
    item.sourcePadding = item.paddingTarget.style.paddingBottom
    header?.classList.add('app-table-persistent-header')
    if (header?.tagName === 'THEAD') header.classList.add('app-table-persistent-thead')
    const setScroll = value => { source.scrollLeft = Math.max(0, Math.min(item.metrics?.maximum || 0, value)); schedule() }
    let drag
    const move = event => {
      if (!drag || event.pointerId !== drag.id) return
      const travel = item.geometry.width - item.metrics.width
      if (travel > 0) setScroll(drag.value + (event.clientX - drag.x) * item.metrics.maximum / travel)
      event.preventDefault()
    }
    const up = event => {
      if (!drag || (event?.pointerId != null && event.pointerId !== drag.id)) return
      drag = null; track.classList.remove('is-dragging')
      doc.removeEventListener('pointermove', move); doc.removeEventListener('pointerup', up); doc.removeEventListener('pointercancel', up); win.removeEventListener('blur', up)
    }
    track.addEventListener('pointerdown', event => {
      if (event.button !== 0 || !item.metrics) return
      event.preventDefault(); track.focus({ preventScroll: true })
      if (event.target !== thumb) setScroll((event.clientX - item.geometry.left - item.metrics.width / 2) * item.metrics.maximum / Math.max(1, item.geometry.width - item.metrics.width))
      drag = { id: event.pointerId, x: event.clientX, value: source.scrollLeft }
      track.classList.add('is-dragging')
      doc.addEventListener('pointermove', move, { passive: false }); doc.addEventListener('pointerup', up); doc.addEventListener('pointercancel', up); win.addEventListener('blur', up)
    })
    track.addEventListener('keydown', event => {
      const next = { ArrowLeft: source.scrollLeft - 40, ArrowRight: source.scrollLeft + 40, PageUp: source.scrollLeft - source.clientWidth, PageDown: source.scrollLeft + source.clientWidth, Home: 0, End: item.metrics?.maximum }
      if (event.key in next) { event.preventDefault(); setScroll(next[event.key]) }
    })
    track.addEventListener('wheel', event => { event.preventDefault(); setScroll(source.scrollLeft + (event.deltaX || event.deltaY)) }, { passive: false })
    const resize = new win.ResizeObserver(schedule)
    resize.observe(root); resize.observe(source); if (header) resize.observe(header)
    item.dispose = () => {
      up(); resize.disconnect(); track.remove()
      if (header) { header.classList.remove('app-table-persistent-header', 'app-table-persistent-thead'); header.style.transform = item.headerTransform }
      source.classList.remove('app-table-horizontal-source'); item.paddingTarget.style.paddingBottom = item.sourcePadding
      if (item.generatedId) source.removeAttribute('id')
    }
    return item
  }
  let sequence = 0
  function refresh() {
    frame = 0
    scaleCache = new WeakMap()
    const candidates = doc.querySelectorAll('.el-table, table, .arrangement-projects')
    const live = new Set()
    for (const root of candidates) {
      const item = descriptor(root)
      if (!item?.source || item.source === doc.documentElement) continue
      live.add(root)
      const old = entries.get(root)
      if (old && (old.header !== item.header || old.source !== item.source)) { old.dispose(); entries.delete(root) }
      if (!entries.has(root)) entries.set(root, bind(item))
    }
    for (const [root, item] of entries) {
      if (!live.has(root) || !root.isConnected) { item.dispose(); entries.delete(root); continue }
      const { header, source, track, thumb } = item
      const rect = root.getBoundingClientRect()
      if (!rect.width || !rect.height || !root.getClientRects().length) { track.hidden = true; continue }
      const clip = clipping(header ? header.parentElement : source)
      // The body's own vertical scrolling must not move a separate ElTable header.
      const bodyClip = clipping(source)
      // Expanded child tables keep their headings below the parent's heading;
      // their horizontal control also stays above the parent's bottom control.
      for (let ancestor = root.parentElement; ancestor; ancestor = ancestor.parentElement) {
        const parent = entries.get(ancestor)
        if (!parent) continue
        const parentHead = parent.header?.getBoundingClientRect()
        if (parentHead && parentHead.top <= clip.top + 1 && parentHead.bottom > clip.top) clip.top = parentHead.bottom
        if (!parent.track.hidden) bodyClip.bottom = Math.min(bodyClip.bottom, parent.track.getBoundingClientRect().top)
      }
      const scale = scaleOf(header || root).y
      const hRect = header?.getBoundingClientRect()
      const geometry = tableScrollGeometry({ root: rect, header: hRect, source: source.getBoundingClientRect(), clip: { ...bodyClip, top: clip.top }, scale, offset: item.offset })
      item.offset = geometry.shift; item.geometry = geometry
      if (header) css(header, 'transform', geometry.shift ? `${item.headerTransform} translateY(${geometry.shift}px)`.trim() : item.headerTransform)
      const horizontal = source.scrollWidth > source.clientWidth + 1
      source.classList.toggle('app-table-horizontal-source', horizontal)
      // Reserve exactly the track height inside the scroll viewport, so the last
      // row remains reachable without adding a blank strip below the scrollbar.
      if (horizontal && !item.padding) { item.padding = true; item.paddingValue = Number.parseFloat(win.getComputedStyle(item.paddingTarget).paddingBottom) || 0 }
      css(item.paddingTarget, 'paddingBottom', horizontal ? `${item.paddingValue + 14 / scaleOf(item.paddingTarget).y}px` : item.sourcePadding)
      track.hidden = !horizontal || !geometry.visible
      if (track.hidden) continue
      const metrics = horizontalThumb(source.clientWidth, source.scrollWidth, source.scrollLeft, geometry.width)
      item.metrics = metrics
      css(track, 'left', `${geometry.left}px`); css(track, 'top', `${geometry.top}px`); css(track, 'width', `${geometry.width}px`); css(track, 'zIndex', `${bodyClip.z}`)
      css(thumb, 'width', `${metrics.width}px`); css(thumb, 'transform', `translateX(${metrics.left}px)`)
      track.setAttribute('aria-valuemax', `${Math.round(metrics.maximum)}`); track.setAttribute('aria-valuenow', `${Math.round(source.scrollLeft)}`)
    }
  }
  const observer = new win.MutationObserver(records => {
    if (records.some(record => !record.target.closest?.('.app-table-horizontal-scroll') && !(record.type === 'attributes' && record.target.classList?.contains('app-table-persistent-header')))) schedule()
  })
  observer.observe(doc.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style', 'hidden', 'open'] })
  doc.addEventListener('scroll', schedule, { capture: true, passive: true }); win.addEventListener('resize', schedule)
  win.visualViewport?.addEventListener('resize', schedule)
  schedule()
  return () => {
    stopped = true; observer.disconnect(); win.cancelAnimationFrame(frame)
    doc.removeEventListener('scroll', schedule, true); win.removeEventListener('resize', schedule); win.visualViewport?.removeEventListener('resize', schedule)
    for (const item of entries.values()) item.dispose()
    entries.clear()
  }
}
