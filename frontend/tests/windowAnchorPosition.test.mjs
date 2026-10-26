import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { reactive, watch, nextTick } from 'vue'
import { notifyWindowAnchors } from '../src/utils/windowAnchorPosition.js'

function harness() {
  const viewport = new EventTarget(), frames = new Map(), cleanup = []
  let frameId = 0, updates = 0
  Object.assign(viewport, {
    Event, innerWidth: 1200, innerHeight: 900,
    requestAnimationFrame(fn) { const id = ++frameId; frames.set(id, fn); return id },
    cancelAnimationFrame(id) { frames.delete(id) },
  })
  viewport.addEventListener('scroll', () => updates++)
  const root = { isConnected: true, ownerDocument: { defaultView: viewport },
    getBoundingClientRect: () => ({ left: 100, top: 80, width: 600, height: 500 }) }
  const source = readFileSync(new URL('../src/composables/useWindowGeometry.js', import.meta.url), 'utf8')
  const { useWindowGeometry } = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replaceAll('export function ', 'function ') + '\n;({useWindowGeometry})', {
    reactive, watch, onBeforeUnmount: fn => cleanup.push(fn), notifyWindowAnchors,
    window: viewport, document: { body: { style: { userSelect: '' } } },
  })
  const geometry = useWindowGeometry(() => root)
  const fire = (type, values = {}) => viewport.dispatchEvent(Object.assign(new Event(type), values))
  const frame = () => { const batch = [...frames.values()]; frames.clear(); batch.forEach(fn => fn()) }
  return { geometry, viewport, root, fire, frame, frames, updates: () => updates,
    dispose: () => cleanup.forEach(fn => fn()),
    start: (edge) => geometry.start({ button: 0, clientX: 100, clientY: 80, preventDefault() {}, stopPropagation() {} }, edge) }
}

test('连续拖动合并到渲染帧，停止后仍校正嵌套浮层，且不派发 resize', async () => {
  const h = harness()
  let resized = 0
  h.viewport.addEventListener('resize', () => resized++)
  h.start()
  for (let n = 1; n <= 20; n++) h.fire('mousemove', { clientX: 100 + n, clientY: 80 + n })
  h.fire('mouseup')
  await nextTick()
  assert.equal(h.frames.size, 1)
  assert.equal(h.updates(), 0)
  assert.equal(h.geometry.state.rect.x, 120)
  h.frame()
  assert.equal(h.updates(), 1)
  h.frame()
  assert.equal(h.updates(), 2)
  assert.equal(resized, 0)
  h.dispose()
})

test('缩放、最大化、还原与复位均更新锚点，鼠标释放后不继续修改窗口', async () => {
  const h = harness()
  h.start('se')
  h.fire('mousemove', { clientX: 200, clientY: 180 })
  h.fire('mouseup')
  assert.equal(h.geometry.state.rect.width, 700)
  h.fire('mousemove', { clientX: 500, clientY: 500 })
  assert.equal(h.geometry.state.rect.width, 700)
  for (const action of [() => {}, h.geometry.maximize, h.geometry.restore, h.geometry.reset]) {
    action()
    await nextTick()
    const before = h.updates()
    h.frame(); h.frame()
    assert.equal(h.updates(), before + 2)
  }
  h.dispose()
})

test('卸载取消待执行的浮层刷新，已移除窗口不派发事件', async () => {
  const h = harness()
  h.geometry.maximize()
  await nextTick()
  assert.equal(h.frames.size, 1)
  h.dispose()
  assert.equal(h.frames.size, 0)
  h.root.isConnected = false
  notifyWindowAnchors(h.root)
  assert.equal(h.updates(), 0)
})
