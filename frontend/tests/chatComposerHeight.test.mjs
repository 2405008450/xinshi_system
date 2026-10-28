import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { computed, ref } from 'vue'

const source = readFileSync(new URL('../src/composables/useChatComposerHeight.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export function', 'function')
function harness({ owner = 'a', saved, viewport = 884, storageBlocked = false } = {}) {
  const values = new Map(saved === undefined ? [] : [[`xinshi.chatComposerHeight.${owner}`, String(saved)]])
  const listeners = new Map()
  let cleanup
  const control = runInNewContext(source + ';useChatComposerHeight()', {
    computed, ref, onBeforeUnmount: fn => { cleanup = fn },
    localStorage: {
      getItem: key => { if (storageBlocked) throw Error('blocked'); return key === 'user_id' ? owner : values.get(key) },
      setItem: (key, value) => values.set(key, value),
    },
    window: { innerHeight: viewport, addEventListener: (key, fn) => listeners.set(key, fn), removeEventListener: key => listeners.delete(key) },
  })
  return { control, values, listeners, cleanup: () => cleanup() }
}

test('默认80px，存储不可用时仍可打开输入区', () => {
  for (const storageBlocked of [false, true]) {
    const h = harness({ storageBlocked })
    assert.equal(h.control.composerStyle.value['--chat-composer-height'], '80px')
    h.cleanup()
  }
})

test('拖动按视口限制高度，结束时按用户保存并清理监听器', () => {
  const h = harness({ viewport: 600 })
  h.control.start({ button: 0, clientY: 500, preventDefault() {} })
  h.listeners.get('pointermove')({ clientY: 200 })
  assert.equal(h.control.composerStyle.value['--chat-composer-height'], '150px')
  h.listeners.get('pointerup')()
  assert.equal(h.values.get('xinshi.chatComposerHeight.a'), '150')
  assert.equal(h.listeners.size, 0)
  h.cleanup()
})

test('恢复用户高度，键盘调整只改当前用户配置', () => {
  const h = harness({ owner: 'b', saved: 96 })
  h.control.resizeByKeyboard({ key: 'ArrowUp', preventDefault() {} })
  assert.equal(h.control.composerStyle.value['--chat-composer-height'], '112px')
  assert.equal(h.values.get('xinshi.chatComposerHeight.b'), '112')
  assert.equal(h.values.has('xinshi.chatComposerHeight.a'), false)
  h.cleanup()
})
