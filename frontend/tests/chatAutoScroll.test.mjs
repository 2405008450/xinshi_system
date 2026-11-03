import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRenderer, nextTick, shallowRef } from 'vue'

// 使用真实 Vue 生命周期，尺寸变化及滚动事件由测试控制。
const source = readFileSync(new URL('../src/composables/useChatAutoScroll.js', import.meta.url), 'utf8')
const vueUrl = new URL('../node_modules/vue/dist/vue.runtime.esm-bundler.js', import.meta.url).href
const { useChatAutoScroll } = await import(`data:text/javascript,${encodeURIComponent(source.replace("from 'vue'", `from '${vueUrl}'`))}`)
const renderer = createRenderer({ createComment: () => ({}), insert() {}, remove() {}, parentNode() {}, nextSibling() {} })

function setup() {
  let resize, disconnected = false, listener, api, top = 0
  globalThis.ResizeObserver = class {
    constructor(callback) { resize = callback }
    observe() {}
    disconnect() { disconnected = true }
  }
  const element = { clientHeight: 200, scrollHeight: 1000, firstElementChild: {}, addEventListener: (_, fn) => { listener = fn }, removeEventListener: () => { listener = null } }
  Object.defineProperty(element, 'scrollTop', { get: () => top, set: value => { top = Math.max(0, Math.min(value, element.scrollHeight - element.clientHeight)) } })
  const viewport = shallowRef(element), active = shallowRef(true)
  const app = renderer.createApp({ setup() { api = useChatAutoScroll(() => viewport.value, () => active.value); return () => null } })
  app.mount({})
  return { element, active, api, resize: () => resize(), scroll: value => { element.scrollTop = value; listener() }, unmount: () => app.unmount(), disconnected: () => disconnected, listener: () => listener }
}

test('首次打开、图片延迟增高及输入区改变高度后持续定位到底部', async () => {
  const s = setup()
  try {
    await s.api.bottom(); assert.equal(s.element.scrollTop, 800)
    s.element.scrollHeight = 1700; s.resize(); assert.equal(s.element.scrollTop, 1500)
    s.element.clientHeight = 100; s.resize(); assert.equal(s.element.scrollTop, 1600)
  } finally { s.unmount() }
})

test('上翻历史时不打断，手动回到底部后恢复跟随', async () => {
  const s = setup()
  try {
    await s.api.bottom(); s.scroll(300)
    s.element.scrollHeight = 1500; s.resize(); assert.equal(s.element.scrollTop, 300)
    s.scroll(1300); s.element.scrollHeight = 1800; s.resize(); assert.equal(s.element.scrollTop, 1600)
  } finally { s.unmount() }
})

test('定位历史及加载更早消息时暂停，返回最新后恢复', async () => {
  const s = setup()
  try {
    await s.api.bottom(); s.api.pause(); s.scroll(800)
    s.element.scrollHeight = 1800; s.resize(); assert.equal(s.element.scrollTop, 800)
    await s.api.bottom(); assert.equal(s.element.scrollTop, 1600)
  } finally { s.unmount() }
})

test('隐藏窗口不滚动，恢复可见后的布局变化继续定位', async () => {
  const s = setup()
  try {
    await s.api.bottom(); s.active.value = false
    s.element.scrollHeight = 1600; s.resize(); assert.equal(s.element.scrollTop, 800)
    s.active.value = true; s.resize(); assert.equal(s.element.scrollTop, 1400)
  } finally { s.unmount() }
})

test('卸载清理尺寸监听和滚动事件', async () => {
  const s = setup(); await nextTick(); s.unmount()
  assert.equal(s.disconnected(), true); assert.equal(s.listener(), null)
})
