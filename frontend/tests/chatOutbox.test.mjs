import test from 'node:test'
import assert from 'node:assert/strict'
import { createOptimisticMessage } from '../src/utils/chatOptimistic.js'
import {
  isRetryableSendError,
  loadOutboxMessages,
  markOutboxInFlight,
  outboxInFlightCount,
  removeOutboxMessage,
  sendWithAutoRetry,
  unmarkOutboxInFlight,
  upsertOutboxMessage,
} from '../src/utils/chatOutbox.js'

function createMemoryStorage() {
  const data = new Map()
  return {
    getItem: key => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: key => data.delete(key),
  }
}

test('发件箱持久化可恢复中断消息，在途消息保持 sending，确认后彻底清除', () => {
  const storage = createMemoryStorage()
  const scope = { userId: 'u1', projectType: 'translation', projectId: 'p1' }
  const msg1 = createOptimisticMessage({ clientMessageId: 'cid-1', senderUserId: 'u1', content: '断网中断的消息', payload: { content: '断网中断的消息', clientMessageId: 'cid-1' } })
  const msg2 = createOptimisticMessage({ clientMessageId: 'cid-2', senderUserId: 'u1', content: '仍在发送中的消息', payload: { content: '仍在发送中的消息', clientMessageId: 'cid-2' } })

  upsertOutboxMessage(scope, msg1, { storage })
  upsertOutboxMessage(scope, msg2, { storage })
  markOutboxInFlight('cid-2')

  try {
    const restored = loadOutboxMessages(scope, { storage })
    assert.equal(restored.length, 2)
    assert.equal(restored[0].clientMessageId, 'cid-1')
    assert.equal(restored[0].optimisticStatus, 'failed')
    assert.ok(restored[0].optimisticError.includes('重试'))
    assert.equal(restored[1].clientMessageId, 'cid-2')
    assert.equal(restored[1].optimisticStatus, 'sending')

    removeOutboxMessage(scope, msg1.id, { storage })
    removeOutboxMessage(scope, 'cid-2', { storage })
    assert.deepEqual(loadOutboxMessages(scope, { storage }), [])
  } finally {
    unmarkOutboxInFlight('cid-2')
  }
})

test('isRetryableSendError 正确区分瞬断与业务错误', () => {
  assert.equal(isRetryableSendError(new Error('Network Error')), true)
  assert.equal(isRetryableSendError({ response: { status: 502 } }), true)
  assert.equal(isRetryableSendError({ response: { status: 504 } }), true)
  assert.equal(isRetryableSendError({ response: { status: 429 } }), true)
  assert.equal(isRetryableSendError({ response: { status: 400 } }), false)
  assert.equal(isRetryableSendError({ response: { status: 403 } }), false)
  assert.equal(isRetryableSendError({ code: 'ERR_CANCELED' }), false)
})

test('sendWithAutoRetry 在瞬断后自动静默重试并在业务错误时立即停止', async () => {
  const slept = []
  let attempts = 0
  const ok = await sendWithAutoRetry(async () => {
    attempts += 1
    if (attempts < 3) throw { response: { status: 502 } }
    return { id: 'srv-ok' }
  }, { delays: [1500, 3000], sleep: async ms => { slept.push(ms) } })

  assert.deepEqual(ok, { id: 'srv-ok' })
  assert.equal(attempts, 3)
  assert.deepEqual(slept, [1500, 3000])

  let forbiddenAttempts = 0
  await assert.rejects(
    () => sendWithAutoRetry(async () => {
      forbiddenAttempts += 1
      throw { response: { status: 403 } }
    }, { delays: [1500, 3000], sleep: async () => {} }),
    err => err.response?.status === 403,
  )
  assert.equal(forbiddenAttempts, 1)
})

test('锁冲突按 Retry-After 错峰重试，并复用待发送消息', async () => {
  const payload = { clientMessageId: 'same-message' }
  const attempts = []
  const delays = []
  await sendWithAutoRetry(async () => {
    attempts.push(payload)
    if (attempts.length === 1) throw { response: { status: 503, headers: { 'retry-after': '2' } } }
  }, { random: () => 0.5, sleep: async ms => { delays.push(ms) } })
  assert.deepEqual(attempts, [payload, payload])
  assert.equal(attempts[0], attempts[1])
  assert.deepEqual(delays, [2250])
})

test('存在在途消息时注册 beforeunload 拦截，全部完成后自动解除', () => {
  const listeners = new Map()
  const prevWindow = globalThis.window
  globalThis.window = {
    addEventListener: (type, fn) => listeners.set(type, fn),
    removeEventListener: (type, fn) => { if (listeners.get(type) === fn) listeners.delete(type) },
  }
  try {
    markOutboxInFlight('cid-unload')
    assert.equal(outboxInFlightCount(), 1)
    assert.ok(listeners.has('beforeunload'))

    let prevented = false
    const evt = { preventDefault: () => { prevented = true }, returnValue: undefined }
    listeners.get('beforeunload')(evt)
    assert.equal(prevented, true)
    assert.equal(evt.returnValue, '')

    unmarkOutboxInFlight('cid-unload')
    assert.equal(outboxInFlightCount(), 0)
    assert.equal(listeners.has('beforeunload'), false)
  } finally {
    globalThis.window = prevWindow
  }
})
