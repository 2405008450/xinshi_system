import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'

function setup(){
 let owner='a';const calls=[]
 const api={get:(path,config)=>new Promise((resolve,reject)=>calls.push({path,config,resolve,reject}))}
 const source=readFileSync(new URL('../src/api/monthlyShifts.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace(/\bexport /g,'')
 const sandbox={api,localStorage:{getItem:()=>owner}}
 runInNewContext(source+'\nthis.readDirectory=getMonthlyShiftDirectory',sandbox)
 return {read:sandbox.readDirectory,calls,setOwner:value=>{owner=value}}
}

test('班次和值班同时加载名单只发一次请求，完成后刷新会重新请求',async()=>{
 const {read,calls}=setup();const first=read(),second=read()
 assert.equal(first,second);assert.equal(calls.length,1);assert.equal(calls[0].config.timeout,30000)
 calls[0].resolve({people:[]});await first
 const refreshed=read();assert.equal(calls.length,2);calls[1].resolve({people:[{id:'new'}]});assert.equal((await refreshed).people[0].id,'new')
})

test('不同用户不共享名单请求，旧响应不会清除新请求，失败后可重试',async()=>{
 const {read,calls,setOwner}=setup();const first=read();setOwner('b');const second=read()
 assert.notEqual(first,second);assert.equal(calls.length,2)
 calls[0].resolve({people:[]});await first;assert.equal(read(),second)
 calls[1].reject(new Error('busy'));await assert.rejects(second,/busy/)
 const retry=read();assert.equal(calls.length,3);calls[2].resolve({people:[]});await retry
})
