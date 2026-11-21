import test from 'node:test'
import assert from 'node:assert/strict'
import { retryDelayMs, withRetryMark } from '../src/utils/requestRetry.js'

const get = { method: 'get', url: '/projects/translation/page' }

test('GET 遇到 503 按 Retry-After 重试一次，并限制等待范围', () => {
  assert.equal(retryDelayMs({ config: get, response: { status: 503, headers: { 'retry-after': '1' } } }), 1000)
  assert.equal(retryDelayMs({ config: get, response: { status: 503, headers: { 'retry-after': '60' } } }), 3000)
  assert.equal(retryDelayMs({ config: get, response: { status: 503, headers: {} } }), 800)
  assert.equal(retryDelayMs({ config: get, response: { status: 502 } }), 800)
})

test('网络中断重试，超时、业务错误、504 不重试', () => {
  assert.equal(retryDelayMs({ config: get, code: 'ERR_NETWORK' }), 800)
  assert.equal(retryDelayMs({ config: get, code: 'ECONNABORTED' }), null)
  assert.equal(retryDelayMs({ config: get, response: { status: 504 } }), null)
  assert.equal(retryDelayMs({ config: get, response: { status: 500 } }), null)
  assert.equal(retryDelayMs({ config: get, response: { status: 401 } }), null)
})

test('写请求、已取消请求、文件下载和已重试过的请求不再重试', () => {
  const busy = { status: 503, headers: { 'retry-after': '1' } }
  for (const method of ['post', 'put', 'patch', 'delete']) assert.equal(retryDelayMs({ config: { ...get, method }, response: busy }), null)
  assert.equal(retryDelayMs({ config: get, code: 'ERR_CANCELED' }), null)
  assert.equal(retryDelayMs({ config: { ...get, signal: { aborted: true } }, response: busy }), null)
  assert.equal(retryDelayMs({ config: { ...get, responseType: 'blob' }, response: busy }), null)
  assert.equal(retryDelayMs({ config: { ...get, retry: false }, response: busy }), null)
  assert.equal(retryDelayMs({ config: withRetryMark(get), response: busy }), null)
})
