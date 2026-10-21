import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { installOfficeSaveShortcut } from '../src/utils/officeSaveShortcut.js'

function surface() {
  const listeners = new Map(), sent = []
  return { sent,
    addEventListener(type, fn) { const group = listeners.get(type) || new Set(); group.add(fn); listeners.set(type, group) },
    removeEventListener(type, fn) { listeners.get(type)?.delete(fn) },
    postMessage(data, origin) { sent.push({ data, origin }) },
    fire(type, event) { for (const fn of listeners.get(type) || []) fn(event) },
  }
}
function key(overrides = {}) {
  return { key: 's', ctrlKey: true, prevented: false, preventDefault() { this.prevented = true }, ...overrides }
}
const channel = 'xinshi-office-save-v1', origin = 'https://office.example.test'

test('只接受当前 iframe、可信源和当前握手 nonce 的保存请求；销毁后停止监听', () => {
  globalThis.window = surface()
  const editor = surface(), frame = { contentWindow: editor }
  let count = 0
  const hook = installOfficeSaveShortcut({ getFrame: () => frame, getOrigin: () => origin, onSave: () => count++ })
  hook.connect()
  const nonce = editor.sent[0].data.nonce
  const event = { source: editor, origin, data: { channel, type: 'save', nonce } }
  for (const bad of [{ ...event, origin: 'https://evil.test' }, { ...event, source: surface() },
    { ...event, data: { ...event.data, nonce: 'wrong' } }, { ...event, data: { ...event.data, channel: 'wrong' } }]) window.fire('message', bad)
  assert.equal(count, 0)
  window.fire('message', event); assert.equal(count, 1)
  hook.reset(); window.fire('message', event); assert.equal(count, 1)
  hook.dispose(); window.fire('keydown', key()); assert.equal(count, 1)
})

test('外层 Ctrl+S / Command+S 阻止浏览器另存为，忽略组合键、输入法和长按重复', () => {
  globalThis.window = surface()
  let count = 0
  const hook = installOfficeSaveShortcut({ getFrame: () => null, getOrigin: () => origin, onSave: () => count++ })
  for (const event of [key(), key({ ctrlKey: false, metaKey: true, key: 'S' })]) {
    window.fire('keydown', event); assert.equal(event.prevented, true)
  }
  for (const overrides of [{ shiftKey: true }, { altKey: true }, { isComposing: true }, { ctrlKey: false }, { key: 'p' }, { repeat: true }]) window.fire('keydown', key(overrides))
  assert.equal(count, 2); hook.dispose()
})

const bridge = readFileSync(new URL('../public/office-save-bridge.v1.js', import.meta.url), 'utf8')
test('iframe 桥只在父窗口握手后工作，保留编辑器原生按键处理并使用精确目标源', () => {
  const editor = surface(), parent = surface(), nonce = '9fc82fbb-0388-48e4-ab0b-5403da1f5c24'
  editor.parent = parent
  vm.runInNewContext(bridge, { window: editor, document: { referrer: 'https://oa.example.test/annotation-office' }, URL })
  editor.fire('keydown', key()); assert.equal(parent.sent.length, 1) // 只有 ready，不擅自拦截其他集成。
  editor.fire('message', { source: parent, origin: 'https://evil.test', data: { channel, type: 'connect', nonce } })
  editor.fire('keydown', key()); assert.equal(parent.sent.length, 1)
  editor.fire('message', { source: parent, origin: 'https://oa.example.test', data: { channel, type: 'connect', nonce } })
  const event = key(); editor.fire('keydown', event)
  assert.equal(event.prevented, true)
  assert.equal(parent.sent.at(-1).data.type, 'save')
  assert.equal(parent.sent.at(-1).origin, 'https://oa.example.test')
  assert.equal(parent.sent.at(-1).data.nonce, nonce)
  const count = parent.sent.length; editor.fire('keydown', key({ repeat: true })); assert.equal(parent.sent.length, count)
})

test('没有合法父页面时桥不启动', () => {
  for (const referrer of ['', 'about:blank', 'file:///test.html']) {
    const editor = surface(); editor.parent = surface()
    assert.doesNotThrow(() => vm.runInNewContext(bridge, { window: editor, document: { referrer }, URL }))
    assert.equal(editor.parent.sent.length, 0)
  }
})
