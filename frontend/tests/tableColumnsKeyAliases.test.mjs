import assert from 'node:assert/strict'
import test from 'node:test'
import { effectScope, nextTick } from 'vue'
import { useTableColumns } from '../src/composables/useTableColumns.js'

const columns = ['orderNo', 'sourceFileName', 'clientShortName', 'emailSubjectPreview'].map((key) => ({ key }))
const defaults = ['orderNo', 'sourceFileName', 'clientShortName']
const options = {
  keyAliases: { projectName: 'sourceFileName' },
  legacyDefaultKeys: [['orderNo', 'projectName', 'clientShortName', 'removedManager']],
}
const storageKey = (user = 'user-1') => `table-columns:translation-alias-test:${user}`

function setup(t, stored) {
  const values = new Map([['user_id', 'user-1']])
  if (stored !== undefined) values.set(storageKey(), stored)
  const originalStorage = globalThis.localStorage
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  }
  const scope = effectScope()
  t.after(() => {
    scope.stop()
    if (originalStorage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = originalStorage
  })
  const open = (overrides = options) => scope.run(() => useTableColumns('translation-alias-test', columns, defaults, overrides))
  return { values, open }
}

test('自定义配置迁移同数量字段键，并持久化去重结果', (t) => {
  const { values, open } = setup(t, JSON.stringify(['projectName', 'emailSubjectPreview']))
  assert.deepEqual(open().selectedKeys.value, ['sourceFileName', 'emailSubjectPreview'])
  assert.deepEqual(JSON.parse(values.get(storageKey())), ['sourceFileName', 'emailSubjectPreview'])
  values.set(storageKey(), JSON.stringify(['projectName', 'sourceFileName', 'emailSubjectPreview', 'removed']))
  assert.deepEqual(open().selectedKeys.value, ['sourceFileName', 'emailSubjectPreview'])
  assert.deepEqual(JSON.parse(values.get(storageKey())), ['sourceFileName', 'emailSubjectPreview'])
})

test('历史默认配置先映射再匹配，并恢复当前默认字段', (t) => {
  const { values, open } = setup(t, JSON.stringify(['orderNo', 'projectName', 'clientShortName', 'removedManager']))
  assert.deepEqual(open().selectedKeys.value, defaults)
  assert.deepEqual(JSON.parse(values.get(storageKey())), defaults)
})

test('全部取消不会因字段迁移而恢复默认，恢复默认可持久化', async (t) => {
  const { values, open } = setup(t, '[]')
  const settings = open()
  assert.deepEqual(settings.selectedKeys.value, [])
  settings.reset()
  await nextTick()
  assert.deepEqual(JSON.parse(values.get(storageKey())), defaults)
  settings.selectedKeys.value = []
  await nextTick()
  assert.deepEqual(open().selectedKeys.value, [])
})

test('迁移按用户隔离，刷新后保留各自自定义选择', async (t) => {
  const { values, open } = setup(t, JSON.stringify(['projectName']))
  assert.deepEqual(open().selectedKeys.value, ['sourceFileName'])
  values.set('user_id', 'user-2')
  const second = open()
  assert.deepEqual(second.selectedKeys.value, defaults)
  second.selectedKeys.value = ['emailSubjectPreview']
  await nextTick()
  assert.deepEqual(open().selectedKeys.value, ['emailSubjectPreview'])
  values.set('user_id', 'user-1')
  assert.deepEqual(open().selectedKeys.value, ['sourceFileName'])
})

test('无配置或损坏配置使用默认值，损坏配置清理', (t) => {
  const { values, open } = setup(t)
  assert.deepEqual(open().selectedKeys.value, defaults)
  for (const invalid of ['bad-json', '{}']) {
    values.set(storageKey(), invalid)
    assert.deepEqual(open().selectedKeys.value, defaults)
    assert.equal(values.has(storageKey()), false)
  }
})

test('未启用映射的模块继续过滤失效字段，不自动显示文件名', (t) => {
  const { values, open } = setup(t, JSON.stringify(['orderNo', 'projectName', 'emailSubjectPreview']))
  assert.deepEqual(open({}).selectedKeys.value, ['orderNo', 'emailSubjectPreview'])
  assert.deepEqual(JSON.parse(values.get(storageKey())), ['orderNo', 'emailSubjectPreview'])
})
