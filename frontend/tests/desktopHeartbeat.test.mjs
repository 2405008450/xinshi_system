import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { chatClientType } from '../src/utils/chatDevice.js'

const source = readFileSync(new URL('../src/composables/useDesktopHeartbeat.js', import.meta.url), 'utf8')
  .replace(/^import .*$/gm, '').replace('export function ', 'function ')
function harness(mobile = false) {
  const mounts=[],unmounts=[],requests=[],subscriptions=new Map(),events=new Map(),timers=new Map()
  let clock=100000,nextTimer=0
  const store=new Map([['token','isolated-token'],['user_id','actor']])
  runInNewContext(source+';useDesktopHeartbeat()',{
    onMounted:fn=>mounts.push(fn),onBeforeUnmount:fn=>unmounts.push(fn),
    crypto:{randomUUID:()=> '12345678-0000-4000-8000-123456789012'},AbortController,
    newChatRequestId:()=> '12345678-0000-4000-8000-123456789012',
    Date:{now:()=>clock},navigator:{userAgent:mobile?'iPhone Mobile':'Windows NT 10.0'},chatClientType,
    localStorage:{getItem:key=>store.get(key)},
    api:{post:(url,data,config)=>new Promise((resolve,reject)=>requests.push({url,data,config,resolve,reject}))},
    fetch:(url,config)=>new Promise((resolve,reject)=>requests.push({url,data:JSON.parse(config.body),config,resolve,reject})),
    subscribe:(type,fn)=>{subscriptions.set(type,fn);return()=>subscriptions.delete(type)},
    window:{setInterval:fn=>{timers.set(++nextTimer,fn);return nextTimer},clearInterval:id=>timers.delete(id),addEventListener:(type,fn)=>events.set(type,fn),removeEventListener:type=>events.delete(type)},
  })
  mounts.forEach(fn=>fn())
  return {requests,subscriptions,events,timers,store,advance:ms=>clock+=ms,
    tick:()=>timers.forEach(fn=>fn()),unmount:()=>unmounts.forEach(fn=>fn())}
}
const flush=async()=>{for(let i=0;i<5;i++)await Promise.resolve()}

test('无需WebSocket连接即可上报电脑在线，心跳节流，网络恢复立即续期',async()=>{
  const h=harness()
  assert.equal(h.requests.length,1)
  assert.equal(h.requests[0].data.active,true)
  h.requests[0].resolve({recorded:true});await flush()
  h.subscriptions.get('presence-heartbeat')();assert.equal(h.requests.length,1)
  h.advance(25000);h.tick();assert.equal(h.requests.length,2)
  h.requests[1].reject(Error('offline'));await flush()
  h.events.get('online')();assert.equal(h.requests.length,3)
  assert.equal(h.requests[2].data.sequence,3)
  h.requests[2].resolve({recorded:true});await flush()
  h.unmount()
  assert.equal(h.requests[3].data.active,false)
  assert.equal(h.requests[3].data.sequence,4)
  assert.equal(h.timers.size,0)
  assert.equal(h.subscriptions.size,0)
})

test('手机不上报电脑在线，退出账号后不继续发送心跳',async()=>{
  const mobile=harness(true);mobile.tick();assert.equal(mobile.requests.length,0);mobile.unmount()
  const h=harness();h.requests[0].resolve({recorded:true});await flush()
  h.store.clear();h.advance(30000);h.tick();h.unmount()
  assert.equal(h.requests.length,1)
})

test('卸载取消旧请求，离线消息使用更高序号防止旧请求复活在线状态',()=>{
  const h=harness();h.unmount()
  assert.equal(h.requests[0].config.signal.aborted,true)
  assert.equal(h.requests[1].data.active,false)
  assert.ok(h.requests[1].data.sequence>h.requests[0].data.sequence)
  assert.equal(h.requests[1].config.keepalive,true)
})

test('关闭页面发送离线，缓存页面恢复后重新上报；退出前先释放且不重复发送',async()=>{
  const h=harness();h.requests[0].resolve({recorded:true});await flush()
  h.events.get('pagehide')()
  assert.equal(h.requests[1].data.active,false)
  h.advance(30000);h.tick();assert.equal(h.requests.length,2)
  h.events.get('pageshow')();assert.equal(h.requests[2].data.active,true)
  h.requests[2].resolve({recorded:true});await flush()
  h.events.get('auth-session-clearing')()
  assert.equal(h.requests[3].data.active,false)
  h.store.clear();h.unmount();assert.equal(h.requests.length,4)
})
