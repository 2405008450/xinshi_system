import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRenderer, shallowRef } from 'vue'
import { computeCenteredScrollTop, createChatMessageScroller } from '../src/utils/chatMessageScroll.js'

function createMockContainer({ clientHeight = 400, scrollHeight = 2000, scrollTop = 0, targetOffsetTop = 1000, targetHeight = 80 } = {}) {
  const listeners = new Map()
  let resizeCallback = null
  const container = {
    clientHeight,
    scrollHeight,
    firstElementChild: {},
    _scrollTop: scrollTop,
    get scrollTop() { return this._scrollTop },
    set scrollTop(val) {
      this._scrollTop = Math.max(0, Math.min(val, Math.max(0, this.scrollHeight - this.clientHeight)))
    },
    getBoundingClientRect: () => ({ top: 100, height: container.clientHeight }),
    addEventListener(event, fn) {
      if (!listeners.has(event)) listeners.set(event, new Set())
      listeners.get(event).add(fn)
    },
    removeEventListener(event, fn) {
      listeners.get(event)?.delete(fn)
    },
    dispatch(event, payload = {}) {
      for (const fn of listeners.get(event) || []) fn(payload)
    },
  }
  const target = {
    isConnected: true,
    offsetTop: targetOffsetTop,
    height: targetHeight,
    getBoundingClientRect: () => ({
      top: 100 + target.offsetTop - container.scrollTop,
      height: target.height,
    }),
  }
  const PrevRO = globalThis.ResizeObserver
  globalThis.ResizeObserver = class {
    constructor(cb) { resizeCallback = cb }
    observe() {}
    disconnect() { resizeCallback = null }
  }
  return {
    container,
    target,
    triggerResize: () => resizeCallback?.(),
    restore: () => { globalThis.ResizeObserver = PrevRO },
  }
}

test('computeCenteredScrollTop 精确居中普通消息并对超长消息保留顶部呼吸间距', () => {
  const env = createMockContainer({ clientHeight: 400, scrollHeight: 2000, scrollTop: 0, targetOffsetTop: 1000, targetHeight: 80 })
  try {
    // 居中: 1000 - (400 - 80)/2 = 840
    assert.equal(computeCenteredScrollTop(env.container, env.target), 840)

    // 超长消息（比视口还高）：对齐顶边并留 16px 间距，而非截断顶部
    env.target.height = 520
    assert.equal(computeCenteredScrollTop(env.container, env.target), 984)
  } finally {
    env.restore()
  }
})

test('createChatMessageScroller 在上方图片撑高后自动二次对齐，用户滚轮打断后立即释放控制权', () => {
  const env = createMockContainer({ clientHeight: 400, scrollHeight: 2000, scrollTop: 0, targetOffsetTop: 1000, targetHeight: 80 })
  const lockEvents = []
  const scroller = createChatMessageScroller({ settleMs: 2000, onLockChange: v => lockEvents.push(v) })
  try {
    scroller.scrollTo(() => env.container, () => env.target)
    assert.equal(env.container.scrollTop, 840)
    assert.equal(scroller.isLocating(), true)
    assert.deepEqual(lockEvents, [true])

    // 模拟目标消息上方的两张截图加载完成，总高度和目标偏移同时增加 260px
    env.container.scrollHeight += 260
    env.target.offsetTop += 260
    env.triggerResize()
    assert.equal(env.container.scrollTop, 1100)

    // 模拟图片 load 事件再次微调高度 +130px
    env.container.scrollHeight += 130
    env.target.offsetTop += 130
    env.container.dispatch('load')
    assert.equal(env.container.scrollTop, 1230)

    // 用户主动滚轮后立即停止守护，后续高度变化不再抢占滚动条
    env.container.dispatch('wheel')
    assert.equal(scroller.isLocating(), false)
    assert.deepEqual(lockEvents, [true, false])
    env.container.scrollTop = 600
    env.container.scrollHeight += 200
    env.target.offsetTop += 200
    env.triggerResize()
    assert.equal(env.container.scrollTop, 600)
  } finally {
    scroller.stop()
    env.restore()
  }
})

test('useChatAutoScroll 在定位锁定期间不会因靠近底部被 onScroll 误吸回最底', async () => {
  const source = readFileSync(new URL('../src/composables/useChatAutoScroll.js', import.meta.url), 'utf8')
  const vueUrl = new URL('../node_modules/vue/dist/vue.runtime.esm-bundler.js', import.meta.url).href
  const { useChatAutoScroll } = await import(`data:text/javascript,${encodeURIComponent(source.replace("from 'vue'", `from '${vueUrl}'`))}`)
  const renderer = createRenderer({ createComment: () => ({}), insert() {}, remove() {}, parentNode() {}, nextSibling() {} })

  let resize, listener, api, top = 0
  const PrevRO = globalThis.ResizeObserver
  globalThis.ResizeObserver = class {
    constructor(cb) { resize = cb }
    observe() {}
    disconnect() {}
  }
  const element = {
    clientHeight: 200,
    scrollHeight: 1000,
    firstElementChild: {},
    addEventListener: (_, fn) => { listener = fn },
    removeEventListener: () => { listener = null },
  }
  Object.defineProperty(element, 'scrollTop', {
    get: () => top,
    set: value => { top = Math.max(0, Math.min(value, element.scrollHeight - element.clientHeight)) },
  })
  const viewport = shallowRef(element)
  const active = shallowRef(true)
  const app = renderer.createApp({ setup() { api = useChatAutoScroll(() => viewport.value, () => active.value); return () => null } })
  app.mount({})
  try {
    await api.bottom()
    assert.equal(element.scrollTop, 800)

    // 进入定位锁定，并模拟程序滚动到靠近底部（gap < 4）
    api.setLocateLock(true)
    element.scrollTop = 798
    listener()
    element.scrollHeight = 1400
    resize()
    // 锁定期间绝不被拉到底部 1200
    assert.equal(element.scrollTop, 798)

    // 解除锁定后不会立刻抢滚，直到用户或业务再次显式回底
    api.setLocateLock(false)
    resize()
    assert.equal(element.scrollTop, 798)
  } finally {
    app.unmount()
    globalThis.ResizeObserver = PrevRO
  }
})

test('三大聊天面板、截图占位与推送序号透传已完整接入精准定位', () => {
  const screenshotText = readFileSync(new URL('../src/components/common/ScreenshotText.vue', import.meta.url), 'utf8')
  const chatConversation = readFileSync(new URL('../src/components/chat/ChatConversation.vue', import.meta.url), 'utf8')
  const projectChatPanel = readFileSync(new URL('../src/components/ProjectChatPanel.vue', import.meta.url), 'utf8')
  const discussion = readFileSync(new URL('../src/components/chat/DiscussionConversation.vue', import.meta.url), 'utf8')
  const dock = readFileSync(new URL('../src/components/chat/ProjectChatDock.vue', import.meta.url), 'utf8')
  const dockStore = readFileSync(new URL('../src/composables/useProjectChatDock.js', import.meta.url), 'utf8')

  assert.match(screenshotText, /class="screenshot-placeholder"|useThumbnail \? 'screenshot-placeholder'/)
  assert.match(screenshotText, /\.screenshot-placeholder\{[^}]*height:130px/)

  assert.match(chatConversation, /createChatMessageScroller/)
  assert.match(chatConversation, /targetMessageSeq/)
  assert.match(chatConversation, /search\(\{ scrollToBottom: !props\.targetMessageId \}\)/)

  assert.match(projectChatPanel, /createChatMessageScroller/)
  assert.match(projectChatPanel, /targetMessageSeq/)
  assert.match(projectChatPanel, /if \(scrollTop <= 2 && !messageScroller\.isLocating\(\)\) loadEarlierMessages\(\)/)
  assert.match(projectChatPanel, /if \(props\.targetMessageId\) return locateMessage\(props\.targetMessageId\)/)

  assert.match(discussion, /createChatMessageScroller/)
  assert.match(discussion, /targetMessageSeq/)
  assert.match(discussion, /const key = id \? `\$\{id\}:\$\{seq\}` : ''/)

  assert.match(dock, /:target-message-seq="chatWindow\.targetMessageSeq"/)
  assert.match(dockStore, /existing\.targetMessageSeq = \+\+targetMessageSequence/)
})
