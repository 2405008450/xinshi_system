import test from 'node:test'
import assert from 'node:assert/strict'
import { createChatImageQueue } from '../src/utils/chatImageQueue.js'

const file = { type: 'image/png', size: 10, name: '截图.png' }
const tick = () => new Promise(resolve => setImmediate(resolve))
function setup(upload = async () => ({ id: 'image-id' })) {
  const items = [], revoked = [], warnings = []
  const queue = createChatImageQueue(items, {
    upload, createUrl: () => `blob:${revoked.length}`, revokeUrl: url => revoked.push(url), warn: text => warnings.push(text)
  })
  return { queue, items, revoked, warnings }
}
test('图片上传成功后保留预览和附件 ID，移除释放资源', async () => {
  const { queue, items, revoked } = setup()
  queue.add([file])
  assert.equal(items[0].status, 'uploading')
  await tick()
  assert.equal(items[0].status, 'ready')
  assert.equal(items[0].attachment.id, 'image-id')
  queue.remove(items[0].key)
  assert.equal(items.length, 0)
  assert.equal(revoked.length, 1)
})
test('失败保留图片，可重试；重复重试不会重复上传', async () => {
  let calls = 0
  const { queue, items } = setup(async () => { if (++calls === 1) throw Error('failed'); return { id: 'retry' } })
  queue.add([file]); await tick()
  assert.equal(items[0].status, 'failed')
  const item = items[0]
  await Promise.all([queue.retry(item), queue.retry(item)])
  assert.equal(calls, 2)
  assert.equal(item.status, 'ready')
})
test('上传中的图片占用九张限额，非法格式和尺寸不会入队', () => {
  const { queue, items, warnings } = setup(() => new Promise(() => {}))
  queue.add([{ ...file, type: 'image/svg+xml' }, { ...file, size: 0 }, { ...file, size: 10485761 }])
  assert.equal(items.length, 0)
  queue.add(Array(12).fill(file))
  assert.equal(items.length, 9)
  assert.equal(warnings.length, 4)
})
test('移除、关闭及切换会话后，旧上传成功或失败都不会污染新草稿', async () => {
  const resolvers = []
  const { queue, items, revoked } = setup(() => new Promise((resolve, reject) => resolvers.push({ resolve, reject })))
  queue.add([file, file])
  queue.remove(items[0].key)
  queue.clear()
  queue.add([file])
  resolvers[0].resolve({ id: 'old' }); resolvers[1].reject(Error('old'))
  await tick()
  assert.equal(items.length, 1)
  assert.equal(items[0].status, 'uploading')
  assert.equal(revoked.length, 2)
  resolvers[2].resolve({ id: 'new' }); await tick()
  assert.equal(items[0].attachment.id, 'new')
})
