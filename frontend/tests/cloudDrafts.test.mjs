import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {pathToFileURL} from 'node:url'
import {resolve} from 'node:path'

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
 source=source.replace("'./autoDraftStore.js'",JSON.stringify(pathToFileURL(resolve('frontend/src/utils/autoDraftStore.js')).href))
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
