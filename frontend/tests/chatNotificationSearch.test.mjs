import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
function setup(){
 const requests=[],counts=[],timers=new Map();let serial=0
 const source=readFileSync(new URL('../src/composables/useChatRequestNotifications.js',import.meta.url),'utf8').replace(/^import .*\n/gm,'').replace('export function useChatRequestNotifications','function useChatRequestNotifications')+'\nuseChatRequestNotifications()'
 const feed=runInNewContext(source,{
  ref:value=>({value}),reactive:value=>value,computed:fn=>({get value(){return fn()}}),onMounted:()=>{},onBeforeUnmount:()=>{},subscribe:()=>()=>{},
  localStorage:{getItem:()=> 'qa-token'},AbortController,CustomEvent:class{},
  window:{dispatchEvent:()=>{},setInterval:()=>1,clearInterval:()=>{}},
  setTimeout:fn=>{timers.set(++serial,fn);return serial},clearTimeout:id=>timers.delete(id),
  getNotificationPage:(params,config)=>new Promise(resolve=>requests.push({params,signal:config.signal,resolve})),
  getUnreadNotificationCount:(params)=>{counts.push(params);return Promise.resolve({count:7})},markNotificationRead:async()=>({}),
 })
 return{feed,requests,counts,timers}
}
const flush=async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve()}
test('组合筛选传给服务端，未读徽标查询不带搜索条件',async()=>{
 const {feed,requests,counts}=setup()
 feed.filters.keyword='Alpha RR-007';feed.filters.notificationType='chat_summary';feed.filters.readStatus='unread';feed.page.value=4
 const work=feed.query();assert.equal(requests[0].params.skip,0);assert.equal(requests[0].params.keyword,'Alpha RR-007');assert.equal(requests[0].params.read_status,'unread')
 assert.equal(counts[0].keyword,undefined);assert.equal(counts[0].notification_type,undefined)
 requests[0].resolve({items:[{id:'one'}],total:1});await work
 assert.equal(feed.total.value,1);assert.equal(feed.unread.value,7)
})
test('输入400ms后查询，清空立即查询；取消旧请求并拒绝旧响应覆盖',async()=>{
 const {feed,requests,timers}=setup()
 const original=feed.refresh();feed.filters.keyword='new';feed.keywordInput()
 assert.equal(requests[0].signal.aborted,true);assert.equal(requests.length,1);assert.equal(timers.size,1)
 const callback=[...timers.values()][0];timers.clear();callback()
 assert.equal(requests.length,2);assert.equal(requests[1].params.keyword,'new')
 feed.filters.keyword='';feed.keywordInput();assert.equal(requests.length,3);assert.equal(requests[1].signal.aborted,true)
 requests[2].resolve({items:[{id:'latest'}],total:1});await flush()
 requests[0].resolve({items:[{id:'old'}],total:50});requests[1].resolve({items:[{id:'older'}],total:20});await original;await flush()
 assert.equal(feed.items.value[0].id,'latest');assert.equal(feed.total.value,1)
})
test('翻页保持筛选，重置清空全部条件并回到第一页',async()=>{
 const {feed,requests}=setup();feed.filters.keyword='编号';feed.filters.readStatus='read'
 const initial=feed.query();requests[0].resolve({items:[],total:90});await initial
 feed.page.value=2;const next=feed.pageChanged();assert.equal(requests[1].params.skip,30);assert.equal(requests[1].params.keyword,'编号')
 requests[1].resolve({items:[],total:90});await next
 const reset=feed.reset();assert.equal(requests[2].params.skip,0);assert.equal(requests[2].params.keyword,undefined);assert.equal(requests[2].params.read_status,'all')
 requests[2].resolve({items:[],total:0});await reset
})
