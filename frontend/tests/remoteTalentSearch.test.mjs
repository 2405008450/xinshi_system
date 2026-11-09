import test from 'node:test'
import assert from 'node:assert/strict'
import {createRemoteTalentSearch} from '../src/utils/remoteTalentSearch.js'

const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}

test('输入新姓名立即清除旧候选，后端返回的无关姓名不会展示',async()=>{
  let state
  const request=deferred()
  const search=createRemoteTalentSearch({fetchOptions:()=>request.promise,onUpdate:value=>state=value})
  const pending=search.search('曹柳云')
  assert.deepEqual(state.items,[])
  request.resolve([{id:1,fullName:'魏昕奕',resourceCode:'RC037470'},{id:2,fullName:'曹柳云',resourceCode:'RC000002'}])
  await pending
  assert.deepEqual(state.items.map(item=>item.fullName),['曹柳云'])
  search.input('赵')
  assert.deepEqual(state.items,[])
})

test('慢请求及取消后的响应不会覆盖最新姓名搜索',async()=>{
  const requests=[],states=[]
  const search=createRemoteTalentSearch({fetchOptions:(keyword,signal)=>{const result=deferred();requests.push({...result,keyword,signal});return result.promise},onUpdate:state=>states.push(state)})
  const old=search.search('曹'),current=search.search('赵')
  assert.equal(requests[0].signal.aborted,true)
  requests[1].resolve([{fullName:'赵红娟'}]);await current
  requests[0].resolve([{fullName:'曹柳云'}]);await old
  assert.deepEqual(states.at(-1).items.map(item=>item.fullName),['赵红娟'])
  search.dispose()
})

test('资源编号和姓名支持多词、忽略大小写、普通文字匹配；清空后重新查询全库',async()=>{
  let state,query
  const search=createRemoteTalentSearch({fetchOptions:async keyword=>{query=keyword;return [{fullName:'曹柳云',resourceCode:'RC000123'},{fullName:'曹柳云',resourceCode:'OTHER'}]},onUpdate:value=>state=value})
  await search.search('rc000 曹')
  assert.equal(state.items.length,1)
  await search.search('%')
  assert.equal(state.items.length,0)
  await search.search('')
  assert.equal(query,'');assert.equal(state.items.length,2)
})

test('搜索失败会清空候选并显示错误，避免保留上一批无关人员',async()=>{
  let state,errors=0
  const search=createRemoteTalentSearch({fetchOptions:async()=>{throw new Error('offline')},onUpdate:value=>state=value,onError:()=>errors++})
  await search.search('曹柳云')
  assert.equal(state.loading,false);assert.deepEqual(state.items,[]);assert.equal(errors,1)
})
