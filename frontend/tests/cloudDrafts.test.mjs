import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'

test('尚未读取云端版本时主动清空，也会清除已有草稿而不是误报冲突',async()=>{
 const storage=new Map(),writes=[];let failWrites=false,server={payload:{form:{projectName:'已保存项目旧草稿'}},revision:7,updated_at:null}
 globalThis.localStorage={getItem:key=>key==='user_id'?'owner':storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}
 globalThis.__clearDraftHarness={api:{get:async()=>({...server}),post:async(_url,{drafts})=>{if(failWrites)throw new Error('offline');return drafts.map(draft=>{writes.push(draft);server={...server,payload:draft.payload,revision:server.revision+1};return {...draft,revision:server.revision,updated_at:null}})}},setTimeout:()=>1,clearTimeout:()=>{}}
 let source=await readFile(new URL('../src/utils/cloudDrafts.js',import.meta.url),'utf8')
 source=source.replace("import {reactive} from 'vue'",'const reactive=value=>value').replace("import api from '@/api/index'",'const {api,setTimeout,clearTimeout}=globalThis.__clearDraftHarness').replace("'./autoDraftStore.js'",JSON.stringify(new URL('../src/utils/autoDraftStore.js',import.meta.url).href))
 try{
  const queue=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
  queue.clearCloudDraft('form:translation-project','create')
  await new Promise(resolve=>setImmediate(resolve))
  await queue.flushCloudDrafts()
  assert.equal(writes.length,1)
  assert.equal(writes[0].revision,7)
  assert.equal(writes[0].payload,null)
  assert.equal((await queue.readCloudDraft('form:translation-project','create')).payload,null)
  assert.equal(queue.cloudDraftState.error,'')
  // 删除同步失败时也要保留本机清除标记，不能重新恢复旧内容。
  server={payload:{form:{projectName:'离线时仍须清空'}},revision:7,updated_at:null};failWrites=true
  queue.clearCloudDraft('form:translation-project','offline-create')
  await new Promise(resolve=>setImmediate(resolve))
  assert.equal((await queue.readCloudDraft('form:translation-project','offline-create')).payload,null)
  failWrites=false;await queue.flushCloudDrafts()
  assert.equal(server.payload,null)
  // 普通新内容仍保留冲突保护，只有主动清除允许删除旧草稿。
  server={payload:{form:{projectName:'另一窗口的内容'}},revision:9,updated_at:null}
  const before=writes.length
  queue.queueCloudDraft('form:translation-project','other-create',{form:{projectName:'本机新内容'}})
  await queue.flushCloudDrafts()
  assert.equal(writes.length,before)
  assert.equal(queue.cloudDraftStatus('form:translation-project','other-create').state,'conflict')
 }finally{delete globalThis.__clearDraftHarness;delete globalThis.localStorage}
})

test('云端合并队列去重、限制批次，慢请求中继续编辑不丢失且不并发',async()=>{
 const records=new Map(),timers=new Map(),sizes=[];let timerId=0,calls=0,active=0,maxActive=0,release
 const harness={setTimeout:(fn,delay)=>{timers.set(++timerId,{fn,delay});return timerId},clearTimeout:id=>timers.delete(id),api:{
  get:async(_url,{params})=>({...params,payload:null,revision:0,updated_at:null}),
  post:async(_url,{drafts})=>{calls++;sizes.push(drafts.length);active++;maxActive=Math.max(maxActive,active);await new Promise(done=>{release=done});const result=drafts.map(item=>{const old=records.get(item.key);const row={namespace:item.namespace,key:item.key,revision:(old?.revision||0)+1,updated_at:'2026-10-31T08:00:00+08:00'};records.set(item.key,{...row,payload:item.payload});return row});active--;return result}
 }}
 globalThis.__draftHarness=harness;globalThis.localStorage={getItem:()=> 'owner'}
 let source=await readFile(new URL('../src/utils/cloudDrafts.js',import.meta.url),'utf8')
 source=source.replace("import {reactive} from 'vue'",'const reactive=value=>value')
 source=source.replace("import api from '@/api/index'",'const {api,setTimeout,clearTimeout}=globalThis.__draftHarness')
 source=source.replace("'./autoDraftStore.js'",JSON.stringify(new URL('../src/utils/autoDraftStore.js',import.meta.url).href))
 try{
  const queue=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
  await queue.readCloudDraft('work-report','day')
  queue.queueCloudDraft('work-report','day',{content:'first'})
  queue.queueCloudDraft('work-report','day',{content:'first'})
  queue.queueCloudDraft('work-report','day',{content:'latest'})
  assert.equal(timers.size,1)
  assert.equal([...timers.values()][0].delay,3000)
  const first=queue.flushCloudDrafts();await Promise.resolve()
  assert.equal(calls,1)
  queue.queueCloudDraft('work-report','day',{content:'edited during request'})
  await queue.flushCloudDrafts();assert.equal(calls,1)
  release();await first
  assert.equal(queue.cloudDraftState.pending,1)
  const second=queue.flushCloudDrafts();await Promise.resolve();release();await second
  assert.equal(maxActive,1)
  assert.equal(records.get('day').payload.content,'edited during request')
  assert.equal(queue.cloudDraftState.pending,0)
  queue.queueCloudDraft('work-report','day',{content:'edited during request'})
  await queue.flushCloudDrafts();assert.equal(calls,2)
  for(let index=0;index<25;index++){await queue.readCloudDraft('global',String(index));queue.queueCloudDraft('global',String(index),{content:index})}
  const third=queue.flushCloudDrafts();await Promise.resolve();release();await third
  assert.equal(sizes.at(-1),20);assert.equal(queue.cloudDraftState.pending,5)
  const fourth=queue.flushCloudDrafts();await Promise.resolve();release();await fourth
  assert.equal(sizes.at(-1),5);assert.equal(queue.cloudDraftState.pending,0);assert.equal(maxActive,1)
 }finally{delete globalThis.__draftHarness;delete globalThis.localStorage}
})
