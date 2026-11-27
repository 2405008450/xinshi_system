import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import { CHAT_WINDOW_REFRESH_MS, createChatWindowFreshness } from '../src/utils/chatWindowFreshness.js'

const source = readFileSync(new URL('../src/components/chat/DiscussionConversation.vue', import.meta.url), 'utf8')

test('讨论断线跨过多页后按游标补齐消息', async () => {
  const refreshSource = source.slice(source.indexOf('async function refresh('), source.indexOf('async function loadEarlier('))
  const start = 9007199254740992n
  const rows = Array.from({ length: 180 }, (_, index) => ({ id: String(start + BigInt(index)) }))
  const messages = { value: rows.slice(0, 5) }
  const cursors = []
  const refresh = runInNewContext(`let requestVersion = 0, controller, pendingFilterReset, searchTimer; ${refreshSource}; refresh`, {
    props: { active: true }, disposed: false, base: 'discussions/room', AbortController, messages,
    messageFreshness: createChatWindowFreshness(CHAT_WINDOW_REFRESH_MS),
    loading: { value: false }, loadingEarlier: { value: false }, pendingNew: { value: false },
    searchParams:()=>({}), searchFiltering:{value:false}, canRefresh:()=>true,
    keyword: { value: '' }, favoritesOnly: { value: false }, error: { value: '' },
    storageReady: { value: true }, atBottom: () => false,
    messageScroller: { isLocating: () => false },
    merge: incoming => { messages.value.push(...incoming) },
    chatRequest: async (path, { params, signal }) => {
      assert.equal(path, 'discussions/room/messages')
      assert.equal(signal.aborted, false)
      if (!params.after) return { items: rows.slice(-50), hasMore: true }
      cursors.push(params.after)
      const waiting = rows.filter(row => BigInt(row.id) > BigInt(params.after))
      return { items: waiting.slice(0, params.limit), hasMore: waiting.length > params.limit }
    },
  })

  await refresh()
  assert.deepEqual(cursors, [rows[4].id, rows[104].id])
  assert.deepEqual(messages.value, rows)
})

test('切回已打开的讨论群时复用消息，过期后补查而不重置', () => {
  let time = 0
  let activate
  let refreshes = 0, scheduled = 0
  const storageReady = { value: false }
  const messageFreshness = createChatWindowFreshness(CHAT_WINDOW_REFRESH_MS, () => time)
  const watcher = source.slice(source.indexOf('watch(() => props.active, active => {'), source.indexOf('const cleanup = ['))
  runInNewContext('let pollTimer, requestVersion = 0, controller, searchTimer, pendingFilterReset;\n' + watcher, {
    watch: (_, effect) => { activate = effect }, storageReady, loading: { value: false }, messageFreshness,
    refresh: reset => {
      assert.equal(reset, true)
      refreshes++
      storageReady.value = true
      messageFreshness.begin()()
    },
    messageScroller:{stop:()=>{}}, pruneMessageWindow:()=>{},
    messageRefresh: { schedule: () => { scheduled++ } },
    atBottom: () => false,
    setInterval: () => 1,
    clearInterval: () => {},
    clearTimeout: () => {},
  })

  activate(true)
  for (let index = 0; index < 5; index++) {
    activate(false)
    time += 1000
    activate(true)
  }
  assert.equal(refreshes, 1)
  assert.equal(scheduled, 0)
  activate(false)
  time = CHAT_WINDOW_REFRESH_MS
  activate(true)
  assert.equal(refreshes, 1)
  assert.equal(scheduled, 1)
})
