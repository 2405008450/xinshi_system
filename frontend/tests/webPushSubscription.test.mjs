import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source = readFileSync(new URL('../src/utils/webPushSubscription.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace(/export async function/g, 'async function')
function setup({ enabled = true, key = 'AQID' } = {}) {
  let actor = 'alice', unsubscribed = 0, registrations = 0, subscriptions = 0
  const posts = [], subscription = {
    toJSON: () => ({ endpoint: 'https://push.example/one', keys: { p256dh: 'key', auth: 'auth' } }),
    unsubscribe: async () => { unsubscribed++ },
  }
  const registration = { pushManager: {
    getSubscription: async () => subscription,
    subscribe: async () => { subscriptions++; return subscription },
  } }
  const api = { get: async () => ({ publicKey: key }), post: async (...args) => posts.push(args) }
  const worker = { register: async () => { registrations++; return registration }, getRegistration: async () => registration, ready: Promise.resolve(registration) }
  const client = runInNewContext(source + ';({syncWebPushSubscription,stopWebPushSubscription})', {
    api, getDesktopNotificationState: () => ({ enabled }), localStorage: { getItem: () => actor },
    window: { isSecureContext: true, PushManager: {}, atob: value => Buffer.from(value, 'base64').toString('binary') },
    navigator: { serviceWorker: worker }, Uint8Array,
  })
  return { ...client, api, posts, worker, switchActor: value => { actor = value },
    get unsubscribed() { return unsubscribed }, get registrations() { return registrations }, get subscriptions() { return subscriptions },
  }
}

test('已授权用户复用现有订阅并向当前账号登记，不重复订阅', async () => {
  const client = setup()
  await client.syncWebPushSubscription()
  assert.equal(client.posts.length, 1)
  assert.equal(client.posts[0][0], '/push/subscribe')
  assert.equal(client.posts[0][1].endpoint, 'https://push.example/one')
  assert.equal(client.subscriptions, 0)
})

test('关闭通知时取消手机订阅，未配置公钥时不登记', async () => {
  const disabled = setup({ enabled: false })
  await disabled.syncWebPushSubscription()
  assert.equal(disabled.unsubscribed, 1)
  assert.equal(disabled.posts.length, 0)
  const missing = setup({ key: null })
  await missing.syncWebPushSubscription()
  assert.equal(missing.posts.length, 0)
})

test('等待公钥期间切换账号，不把原账号的订阅写入新账号', async () => {
  const client = setup()
  let release
  client.api.get = () => new Promise(resolve => { release = resolve })
  const pending = client.syncWebPushSubscription()
  await new Promise(resolve => setImmediate(resolve))
  client.switchActor('bob')
  release({ publicKey: 'AQID' })
  await pending
  assert.equal(client.posts.length, 0)
})

test('未登录时不注册，退出账号可撤销订阅', async () => {
  const client = setup()
  client.switchActor(null)
  await client.syncWebPushSubscription()
  assert.equal(client.registrations, 0)
  await client.stopWebPushSubscription()
  assert.equal(client.unsubscribed, 1)
})
