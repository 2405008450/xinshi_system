import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'

test('跨端提示按 HTTP 确认的游标补拉，即使已先收到一条更晚的实时消息', async () => {
  const source = readFileSync(new URL('../src/components/chat/ChatConversation.vue', import.meta.url), 'utf8')
  const syncSource = source.slice(source.indexOf('async function sync()'), source.indexOf('async function returnLatest()'))
  const row = sequenceNo => ({ id: String(sequenceNo), sequenceNo })
  const messages = { value: [row(10), row(14)] }
  const requests = []
  const run = runInNewContext(`
    let syncedSequence = 10, refreshLoadedMessages = false;
    ${syncSource};
    ({ sync, cursor: () => syncedSequence })
  `, {
    props: { projectId: 'room', active: true }, initialized: true, disposed: false, generation: 0,
    loading: { value: false }, viewingHistory: { value: false }, atBottom: () => true,
    messageFreshness: { begin: () => () => {} }, canRefresh: () => true,
    error: { value: '' }, messages, pendingNew: { value: 0 }, bottom: async () => {},
    merge: incoming => {
      const byId = new Map([...messages.value, ...incoming].map(item => [item.id, item]))
      messages.value = [...byId.values()].sort((a, b) => a.sequenceNo - b.sequenceNo)
    },
    request: async (_, path, options) => {
      requests.push([path, options.params.after])
      return options.params.after === 10
        ? { items: [row(11), row(12)], hasMore: true }
        : { items: [row(13), row(14)], hasMore: false }
    },
  })

  await run.sync()
  assert.deepEqual(requests, [['timeline', 10], ['timeline', 12]])
  assert.deepEqual(messages.value.map(item => item.sequenceNo), [10, 11, 12, 13, 14])
  assert.equal(run.cursor(), 14)
})
