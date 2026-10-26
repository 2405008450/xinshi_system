import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { computed, ref, watch } from 'vue'
import { chatDateLabel, chatMessageTime } from '../src/utils/chatLayout.js'

function harness(storage = new Map()) {
  let listener
  const source = readFileSync(new URL('../src/composables/useChatTimeDisplay.js', import.meta.url), 'utf8')
  const api = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replace(/export function /g, 'function ') + '\n;useChatTimeDisplay', {
    computed, ref, watch, chatDateLabel, chatMessageTime,
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    window: { addEventListener: (_event, callback) => { listener = callback } },
  })
  return { api, storage, storageEvent: event => listener(event) }
}

test('同账号所有会话即时共享设置，刷新后恢复，其他账号独立使用默认值', () => {
  const h = harness(new Map([['user_id', 'alice']]))
  const first = h.api(), second = h.api()
  assert.equal(first.mode.value, 'default')
  first.mode.value = 'time'
  assert.equal(second.mode.value, 'time')
  assert.equal(second.showMessageTime.value, true)
  assert.equal(second.showMessageDates.value, false)
  assert.equal(harness(h.storage).api().mode.value, 'time')
  h.storage.set('user_id', 'bob')
  assert.equal(h.api().mode.value, 'default')
  assert.equal(first.mode.value, 'time')
})

test('隐藏时间也隐藏日期分隔；其他标签页修改可同步，无效偏好回退默认显示', () => {
  const h = harness(new Map([['user_id', 'alice'], ['xinshi.chatTimeDisplay.alice', 'invalid']]))
  const state = h.api()
  assert.equal(state.mode.value, 'default')
  h.storageEvent({ key: 'xinshi.chatTimeDisplay.alice', newValue: 'hidden' })
  assert.equal(state.showMessageTime.value, false)
  assert.equal(state.showMessageDates.value, false)
  h.storageEvent({ key: 'xinshi.chatTimeDisplay.alice', newValue: 'no-year' })
  assert.equal(state.showMessageDates.value, true)
})
