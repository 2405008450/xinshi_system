import { createChatNotificationFeed, isPersistentChatNotification, isVisibleConversation } from '../src/utils/chatNotificationPolicy.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { createNotificationAcknowledgements } from '../src/utils/notificationAcknowledgements.js'
import { isChatNotification, isChatMentionNotification, isChatAttentionNotification, CONVERSATION_NOTIFICATION_TYPES } from '../src/utils/notificationChannels.js'

function browsers() {
  const data = new Map([['user_id', 'alice'], ['token', 'test-token']]), targets = []
  const storage = {
    getItem: key => data.get(key) ?? null,
    setItem(key, value) {
      data.set(key, value)
      for (const target of targets) target.dispatchEvent(Object.assign(new Event('storage'), { key, newValue: value, storageArea: storage }))
    },
  }
  function tab() {
    const target = new EventTarget(); targets.push(target)
    return { target, acknowledgements: createNotificationAcknowledgements({ storage: () => storage, target }) }
  }
  return { storage, tab }
}

test('确认后立即通知其他标签页，刷新后保留；同一账号的新通知仍可提醒', () => {
  const browser = browsers(), a = browser.tab(), b = browser.tab(), received = []
  const unsubscribe = b.acknowledgements.subscribe(id => received.push(id))
  a.acknowledgements.acknowledge('invite/1')
  assert.deepEqual(received, ['invite/1'])
  assert.equal(b.acknowledgements.has('invite/1'), true)
  assert.equal(browser.tab().acknowledgements.has('invite/1'), true)
  assert.equal(b.acknowledgements.has('invite/2'), false)
  unsubscribe(); a.acknowledgements.acknowledge('invite/2')
  assert.deepEqual(received, ['invite/1'])
})

test('多标签页分别确认不同通知不会覆盖；账号之间互相隔离', () => {
  const browser = browsers(), a = browser.tab(), b = browser.tab()
  a.acknowledgements.acknowledge('one'); b.acknowledgements.acknowledge('two')
  assert.equal(a.acknowledgements.has('two'), true)
  browser.storage.setItem('user_id', 'bob')
  assert.equal(a.acknowledgements.has('one'), false)
  browser.storage.setItem('user_id', 'alice')
  assert.equal(a.acknowledgements.has('one'), true)
})

test('存储不可写时保留当前标签页确认结果，且不会重复回调', () => {
  const store = createNotificationAcknowledgements({ storage: () => ({ getItem: () => null, setItem: () => { throw Error('blocked') } }), userId: () => 'alice', target: new EventTarget() })
  const received = []; store.subscribe(id => received.push(id))
  store.acknowledge('one'); store.acknowledge('one')
  assert.equal(store.has('one'), true)
  assert.deepEqual(received, ['one'])
})

const source = readFileSync(new URL('../src/composables/useChatNotifications.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export function useChatNotifications', 'function useChatNotifications')
function mountChat(browser, item, markRead = async () => {}, desktopEnabled = true, overrides = {}) {
  const tab = browser.tab(), mounts = [], unmounts = [], popups = [], subscriptions = {}, opened = [], desktops = []
  runInNewContext(`${source}; useChatNotifications()`, {
    notificationAcknowledgements: tab.acknowledgements,
    createChatNotificationFeed, CONVERSATION_NOTIFICATION_TYPES, nextTick: async()=>{}, h: () => ({}), onMounted: fn => mounts.push(fn), onBeforeUnmount: fn => unmounts.push(fn),
    useProjectChatDock: () => ({ openChat: value => opened.push(value) }),
    ElMessage: { info() {}, error() {} },
    ElNotification: options => { const popup = { options, closed: false, close() { if (!this.closed) { this.closed = true; options.onClose() } } }; popups.push(popup); return popup },
    getNotifications: async () => [{ ...item }], markNotificationRead: markRead,
    subscribe: (name, callback) => { subscriptions[name] = callback; return () => {} },
    showDesktopNotification: (notification, onClick) => { if (!desktopEnabled) return false; desktops.push({notification,onClick}); return true }, isChatNotification, isChatMentionNotification, isChatAttentionNotification,
    localStorage: browser.storage, window: { focus() {}, setInterval() {}, clearInterval() {} }, AbortController, ...overrides,
  })
  mounts.forEach(fn => fn())
  return { tab, popups, desktops, subscriptions, opened, unmount: () => unmounts.forEach(fn => fn()) }
}
const invite = { id: 'invite', notification_type: 'annotation_project_chat_invite', related_project_type: 'annotation', related_entity_id: 'project', title: '项目群聊邀请' }
const flush = () => new Promise(resolve => setImmediate(resolve))

test('仅 @ 提及产生 Windows 通知；普通消息与邀请不产生任何浮窗', async () => {
 const browser=browsers(), a=mountChat(browser,invite)
 await flush()
 assert.equal(a.popups.length,0);assert.equal(a.desktops.length,0)
 for (const type of ['project_chat','direct_chat','direct_chat_invite','annotation_project_chat_invite']) a.subscriptions.notification({notification:{...invite,id:type,notification_type:type}})
 assert.equal(a.desktops.length,0)
 a.subscriptions.notification({notification:{...invite,id:'at-me',notification_type:'direct_chat_mention'}})
 assert.equal(a.desktops.length,1);assert.equal(a.popups.length,0)
 a.unmount()
})

test('桌面通知不可用时不回退网页弹窗，也不将未读信息标为已读', async()=>{
 const browser=browsers(),mention={...invite,id:'at',notification_type:'annotation_project_chat_mention'}
 let reads=0
 const a=mountChat(browser,mention,async()=>{reads++},false)
 await flush();a.subscriptions.foreground();await flush()
 assert.equal(a.popups.length,0);assert.equal(a.desktops.length,0);assert.equal(reads,0)
 assert.equal(a.tab.acknowledgements.has('at'),false)
 a.unmount()
})

test('点击 Windows 通知打开会话并保存已读；重新登录不重弹', async()=>{
 const browser=browsers(),mention={...invite,id:'at',notification_type:'annotation_project_chat_mention'}
 const a=mountChat(browser,mention)
 await flush()
 await a.desktops[0].onClick()
 assert.equal(a.opened.length,1);assert.equal(a.tab.acknowledgements.has('at'),true)
 a.unmount()
 const b=mountChat(browser,mention)
 await flush()
 assert.equal(b.desktops.length,0);assert.equal(b.popups.length,0)
 b.unmount()
})

test('轮询、重连、恢复前台不重复发 Windows 通知；新 @ 正常提醒', async()=>{
 const browser=browsers(),mention={...invite,id:'at',notification_type:'annotation_project_chat_mention'}
 const a=mountChat(browser,mention)
 await flush();a.subscriptions.foreground();await flush();a.subscriptions.connected();await flush()
 assert.equal(a.desktops.length,1)
 a.subscriptions.notification({notification:{...mention,id:'new-at'}})
 assert.equal(a.desktops.length,2)
 a.subscriptions.notification({notification:{...mention,id:'read-at',is_read:true}})
 assert.equal(a.desktops.length,2);assert.equal(a.popups.length,0)
 a.unmount()
})

test('服务端已读记录持久化到当前账号，下次登录不会重弹，未读新消息仍可提醒', () => {
  const browser = browsers(), first = browser.tab(), closed = []
  browser.tab().acknowledgements.subscribe(id => closed.push(id))
  first.acknowledgements.rememberRead([{id:'read-on-another-entry',is_read:true},{id:'new',is_read:false}])
  assert.deepEqual(closed,['read-on-another-entry'])
  browser.storage.setItem('user_id','')
  browser.storage.setItem('user_id','alice')
  const nextLogin=browser.tab()
  assert.equal(nextLogin.acknowledgements.has('read-on-another-entry'),true)
  assert.equal(nextLogin.acknowledgements.has('new'),false)
})

test('已读请求返回时已切换账号，不污染新账号，也不接受无账号响应', () => {
  const browser=browsers(), tab=browser.tab(), actor=tab.acknowledgements.actor()
  browser.storage.setItem('user_id','bob')
  tab.acknowledgements.rememberRead([{id:'alice-only',is_read:true}],actor)
  assert.equal(tab.acknowledgements.has('alice-only'),false)
  browser.storage.setItem('user_id','alice')
  assert.equal(tab.acknowledgements.has('alice-only'),false)
  tab.acknowledgements.rememberRead([{id:'anonymous',is_read:true}],null)
  assert.equal(tab.acknowledgements.has('anonymous'),false)
})

test('通知接口统一同步列表及分页已读结果，标已读失败不会提前记住', async () => {
  const browser=browsers(), tab=browser.tab()
  const rows=[{id:'history',is_read:true},{id:'fresh',is_read:false}]
  let fail=false
  const api={get:async path=>path.endsWith('/page')?{items:rows,total:2}:rows,post:async()=>{if(fail)throw Error('offline');return {is_read:true}}}
  const apiSource=readFileSync(new URL('../src/api/notifications.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace(/export const /g,'const ')
  const client=runInNewContext(`${apiSource}; ({getNotifications,getNotificationPage,markNotificationRead})`,{api,notificationAcknowledgements:tab.acknowledgements})
  assert.equal(await client.getNotifications(),rows)
  assert.equal(tab.acknowledgements.has('history'),true)
  assert.equal(tab.acknowledgements.has('fresh'),false)
  assert.equal((await client.getNotificationPage()).total,2)
  await client.markNotificationRead('read-in-list')
  assert.equal(browser.tab().acknowledgements.has('read-in-list'),true)
  fail=true
  await assert.rejects(client.markNotificationRead('failed'),/offline/)
  assert.equal(tab.acknowledgements.has('failed'),false)
})

test('总结同步与资源需求只通过会话通知发送 Windows 提醒，不生成网页浮窗',async()=>{
 const browser=browsers(),a=mountChat(browser,invite)
 await flush()
 for(const type of ['chat_summary','resource_request_dispatch']) a.subscriptions.notification({notification:{id:type,notification_type:type,title:'会话业务通知'}})
 assert.equal(a.desktops.length,2)
 assert.equal(a.popups.length,0)
 a.unmount()
})


test('普通私聊历史与实时消息都不产生浮窗', async () => {
  const browser = browsers(), item = { ...invite, id: 'old-direct', notification_type: 'direct_chat' }
  const mounted = mountChat(browser, item)
  await flush()
  mounted.subscriptions.notification({ notification: { ...item, id: 'new-direct' } })
  assert.equal(mounted.popups.length, 0)
  assert.equal(mounted.desktops.length, 0)
  mounted.unmount()
})

test('服务端已读轮询同步确认，不再重复发送桌面通知', async () => {
  const browser = browsers(); let read = false
  const item = { ...invite, id: 'mention', notification_type: 'direct_chat_mention' }
  const mounted = mountChat(browser, item, undefined, true, {
    getNotifications: async params => params.channel === 'chat' ? [{ ...item, is_read: read }] : [],
  })
  await flush()
  assert.equal(mounted.desktops.length, 1)
  read = true
  mounted.subscriptions.connected(); await flush()
  assert.equal(mounted.tab.acknowledgements.has(item.id), true)
  assert.equal(mounted.desktops.length, 1)
  mounted.unmount()
})

test('断线超过一页仍补齐提及通知，重连不重弹', async () => {
  const browser = browsers(); let rows = []
  const mounted = mountChat(browser, {}, undefined, true, {
    getNotifications: async params => params.channel === 'chat'
      ? rows.slice(params.skip || 0, (params.skip || 0) + params.limit) : [],
  })
  await flush()
  rows = Array.from({ length: 235 }, (_, i) => ({ ...invite, id: `mention-${i}`, notification_type: 'direct_chat_mention', created_at: '2026-10-28T10:00:00+08:00' }))
  mounted.subscriptions.connected(); await flush()
  assert.equal(mounted.desktops.length, 235)
  mounted.subscriptions.connected(); await flush()
  assert.equal(mounted.desktops.length, 235)
  mounted.unmount()
})
