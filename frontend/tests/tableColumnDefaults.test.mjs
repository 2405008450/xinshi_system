import test from 'node:test'
import assert from 'node:assert/strict'
import { createTableColumnDefaults } from '../src/utils/tableColumnDefaults.js'

function fixture() {
  const values = new Map()
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
  const open = (moduleKey = 'annotation', userKey = 'alice', section = 'main') => createTableColumnDefaults({ moduleKey, userKey, section, storage })
  return { values, open }
}
const columns = [{ key: 'orderNo' }, { key: 'projectName' }, { key: 'status' }]

test('保存完整选择快照，后续临时勾选不影响我的默认，刷新后可恢复', () => {
  const { open } = fixture(), settings = open(), selected = ['status', 'orderNo']
  settings.save(selected, columns)
  selected.push('projectName')
  assert.deepEqual(open().restore(columns), ['orderNo', 'status'])
  assert.equal(open().has(), true)
})

test('个人默认按账号、业务模块和主子表分别隔离', () => {
  const { open } = fixture()
  open().save(['orderNo'], columns)
  open('annotation', 'bob').save(['status'], columns)
  open('translation').save(['projectName'], columns)
  open('annotation', 'alice', 'secondary').save(['status', 'projectName'], columns)
  assert.deepEqual(open().restore(columns), ['orderNo'])
  assert.deepEqual(open('annotation', 'bob').restore(columns), ['status'])
  assert.deepEqual(open('translation').restore(columns), ['projectName'])
  assert.deepEqual(open('annotation', 'alice', 'secondary').restore(columns), ['projectName', 'status'])
})

test('全部取消可以保存为空默认，与从未保存区分', () => {
  const { open } = fixture()
  assert.equal(open().has(), false)
  assert.equal(open().restore(columns), null)
  open().save([], columns)
  assert.equal(open().has(), true)
  assert.deepEqual(open().restore(columns), [])
})

test('恢复时按当前字段清单过滤失效字段，动态字段暂未加载不会破坏原快照', () => {
  const { open } = fixture()
  open().save(['orderNo', 'status', 'removed', 'orderNo'], columns)
  assert.deepEqual(open().restore([{ key: 'orderNo' }]), ['orderNo'])
  assert.deepEqual(open().restore([]), [])
  assert.deepEqual(open().restore(columns), ['orderNo', 'status'])
})

test('损坏或旧格式配置会被清理，不误用为有效的空默认', () => {
  const { values, open } = fixture()
  open().save(['status'], columns)
  const key = [...values.keys()][0]
  for (const invalid of ['broken', '{}', '[null]', '[{}]']) {
    values.set(key, invalid)
    assert.equal(open().has(), false)
    assert.equal(values.has(key), false)
  }
})
