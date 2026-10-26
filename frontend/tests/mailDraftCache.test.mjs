import test from 'node:test'
import assert from 'node:assert/strict'
import { createRenderer, h, reactive } from 'vue'
import { createMailDraftStore, normalizeMailDraftFields, useMailDraftCache } from '../src/composables/useMailDraftCache.js'

function fixture() {
  const rows = new Map()
  const storage = { getItem: key => rows.get(key) ?? null, setItem: (key, value) => rows.set(key, value), removeItem: key => rows.delete(key) }
  let user = 'a'
  let now = Date.parse('2026-10-26T08:00:00+08:00')
  const store = createMailDraftStore({ storage: () => storage, user: () => user, now: () => now })
  return { rows, storage, store, user: value => { user = value }, advance: value => { now += value } }
}

test('用户及业务对象隔离，旧编辑器不能写入新账号', () => {
  const f = fixture()
  f.store.save('project:1', { body: '草稿' }, { body: '默认' })
  const owner = f.store.storageKey()
  assert.equal(f.store.restore('project:1').fields.body, '草稿')
  assert.equal(f.store.restore('project:2'), null)
  f.user('b')
  assert.equal(f.store.restore('project:1'), null)
  f.store.save('project:1', { body: '泄漏' }, {}, owner)
  assert.equal(f.store.restore('project:1'), null)
  f.user('a')
  assert.equal(f.store.restore('project:1').fields.body, '草稿')
})

test('基线比较、恢复默认删除、发送成功清除', () => {
  const { store } = fixture()
  store.save('x', { body: '默认' }, { body: '默认' })
  assert.equal(store.restore('x'), null)
  store.save('x', { body: '编辑' }, { body: '默认' })
  assert.ok(store.restore('x'))
  store.save('x', { body: '默认' }, { body: '默认' })
  assert.equal(store.restore('x'), null)
  store.save('x', { body: '编辑' }, { body: '默认' })
  store.clear('x')
  assert.equal(store.restore('x'), null)
})

test('7 天有效期边界，未修改内容不会延长有效期，时间明确为 UTC+8', () => {
  const f = fixture()
  f.store.save('x', { body: '编辑' }, {})
  assert.equal(f.store.restore('x').savedAt, '2026-10-26T08:00:00+08:00')
  f.advance(7 * 86400000 - 1)
  f.store.save('x', { body: '编辑' }, {})
  assert.equal(f.store.restore('x').savedAt, '2026-10-26T08:00:00+08:00')
  f.advance(1)
  assert.equal(f.store.restore('x'), null)
})

test('最多保留 30 条，淘汰最旧草稿', () => {
  const f = fixture()
  for (let i = 0; i < 31; i++) {
    f.store.save(`x${i}`, { body: `${i}` }, {})
    f.advance(1000)
  }
  assert.equal(f.store.restore('x0'), null)
  assert.ok(f.store.restore('x30'))
  assert.equal(Object.keys(JSON.parse(f.rows.get('mail-drafts:a'))).length, 30)
})

test('同秒写入达到上限时保留新草稿，只缓存修改过的字段', () => {
  const f = fixture()
  for (let i = 0; i < 31; i++) f.store.save(`x${i}`, { body: `${i}`, subject: '系统主题' }, { subject: '系统主题' })
  assert.equal(f.store.restore('x0'), null)
  assert.deepEqual(f.store.restore('x30').fields, { body: '30' })
})

test('损坏内容、无效时间、禁用存储和容量不足均降级', () => {
  const f = fixture()
  for (const raw of ['{', 'null', '[]', '1', '{"x":{"savedAt":"invalid","fields":{}}}']) {
    f.rows.set('mail-drafts:a', raw)
    assert.equal(f.store.restore('x'), null)
  }
  const store = createMailDraftStore({ storage: () => { throw new Error('blocked') } })
  assert.doesNotThrow(() => { store.save('x', {}, {}); store.clear('x') })
  assert.equal(store.restore('x'), null)
  f.storage.setItem = () => { throw new Error('quota') }
  assert.doesNotThrow(() => f.store.save('x', { body: '编辑' }, {}))
})

test('图片 ID 与元数据保留，临时 Blob 地址不持久化且不触发伪修改', () => {
  const fields = src => ({ body: '文字', html: `<p>文字</p><img src="${src}" data-mail-image-id="123">`, images: [{ id: '123' }] })
  const { store } = fixture()
  store.save('x', fields('blob:first'), fields('blob:second'))
  assert.equal(store.restore('x'), null)
  assert.equal(normalizeMailDraftFields(fields('blob:abc')).html, '<p>文字</p><img src="" data-mail-image-id="123">')
})

test('400ms 防抖、关闭立即落盘、暂停后重置不覆盖、清除不复活、卸载落盘', async () => {
  const f = fixture()
  globalThis.localStorage = f.storage
  f.storage.setItem('user_id', 'qa')
  let cache
  const form = reactive({ body: '默认' })
  const renderer = createRenderer({ createElement: () => ({}), insert() {}, remove() {}, setElementText() {}, patchProp() {} })
  const app = renderer.createApp({ setup() { cache = useMailDraftCache(); return () => h('div') } })
  app.mount({})
  try {
    cache.track('x', () => ({ ...form }), { ...form })
    form.body = '编辑'
    assert.equal(f.rows.has('mail-drafts:qa'), false)
    await new Promise(resolve => setTimeout(resolve, 450))
    assert.equal(cache.restore('x').fields.body, '编辑')
    form.body = '关闭前编辑'
    cache.pause()
    form.body = ''
    assert.equal(cache.restore('x').fields.body, '关闭前编辑')
    form.body = '重开编辑'
    cache.track('x', () => ({ ...form }), { body: '默认' })
    cache.clear()
    cache.pause()
    assert.equal(cache.restore('x'), null)
    cache.track('x', () => ({ ...form }), { body: '默认' })
    form.body = '卸载前编辑'
  } finally { app.unmount(); delete globalThis.localStorage }
  assert.equal(JSON.parse(f.rows.get('mail-drafts:qa')).x.fields.body, '卸载前编辑')
})
