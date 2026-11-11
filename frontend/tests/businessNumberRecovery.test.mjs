import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
const source=readFileSync(new URL('../src/composables/useBusinessNumber.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace('export function ','function ')
const flush=async()=>{for(let i=0;i<15;i++)await Promise.resolve()}
function harness(){
 const model={orderNo:'',projectName:'未保存内容'},store=new Map([['user_id','actor'],['token','isolated']]),requests=[],timers=new Map(),timeouts=new Map(),events=new Map(),documentEvents=new Map(),unmounts=[],leases=new Map();let next=0
 const options={model:()=>model,field:()=>'orderNo',kind:()=>'translation',parent:()=>null,date:()=>null,active:()=>true}
 const context={ref:value=>({value}),watch:(getter,callback,config)=>{if(config?.immediate)callback(getter())},onBeforeUnmount:fn=>unmounts.push(fn),localStorage:{getItem:key=>store.get(key)},api:{post:(url,data)=>new Promise((resolve,reject)=>requests.push({url,data,resolve,reject}))},businessNumberLeases:leases,registerBusinessNumberField:()=>{},newNumberWindowId:()=>`window-${++next}`,fetch:()=>Promise.resolve(),setInterval:fn=>{timers.set(++next,fn);return next},clearInterval:id=>timers.delete(id),setTimeout:(fn,delay)=>{timeouts.set(++next,{fn,delay});return next},clearTimeout:id=>timeouts.delete(id),window:{addEventListener:(name,fn)=>events.set(name,fn),removeEventListener:name=>events.delete(name)},document:{visibilityState:'visible',addEventListener:(name,fn)=>documentEvents.set(name,fn),removeEventListener:name=>documentEvents.delete(name)},options}
 runInNewContext(source+';this.result=useBusinessNumber(options)',context)
 return {model,requests,timers,timeouts,retry:()=>{for(const [id,item] of [...timeouts]){timeouts.delete(id);item.fn()}},events,documentEvents,leases,store,result:context.result,tick:()=>[...timers.values()].forEach(fn=>fn()),unmount:()=>unmounts.forEach(fn=>fn())}
}
async function opened(){const h=harness();h.requests[0].resolve({token:'lease-a',number:'TP-261108-001'});await flush();return h}
test('临时失败后续期成功清除错误，保存前验证，保留原编号及录入',async()=>{
 const h=await opened();h.tick();h.requests[1].reject({response:{status:503}});await flush();assert.match(h.result.error.value,/订单号暂时无法确认，系统正在重试/)
 h.tick();h.requests[2].resolve({ok:true});await flush();assert.equal(h.result.error.value,'');assert.equal(h.model.orderNo,'TP-261108-001')
 const ready=h.result.ensure();assert.match(h.requests[3].url,/heartbeat$/);h.requests[3].resolve({ok:true});assert.equal(await ready,true);assert.equal(h.model.projectName,'未保存内容')
})

test('连接中断和繁忙先短延迟重试，保留原编号，恢复后可以继续保存',async()=>{
 const h=await opened();h.tick();h.requests[1].reject({code:'ERR_NETWORK'});await flush()
 assert.equal([...h.timeouts.values()][0].delay,2000)
 h.retry();assert.equal(h.requests[2].url,'/business-numbers/lease-a/heartbeat')
 h.requests[2].reject({response:{status:503}});await flush()
 assert.equal([...h.timeouts.values()][0].delay,4000)
 h.retry();h.requests[3].resolve({ok:true});await flush()
 assert.equal(h.result.error.value,'');assert.equal(h.timeouts.size,0)
 assert.equal(h.model.orderNo,'TP-261108-001');assert.equal(h.model.projectName,'未保存内容')
 const ready=h.result.ensure();h.requests[4].resolve({ok:true});assert.equal(await ready,true)
})

test('关闭表单后取消短延迟重试，不再发送旧窗口请求',async()=>{
 const h=await opened();h.tick();h.requests[1].reject({response:{status:502}});await flush()
 assert.equal(h.timeouts.size,1);h.unmount();assert.equal(h.timeouts.size,0)
 const count=h.requests.length;h.retry();assert.equal(h.requests.length,count)
})
test('过期409重新申请编号，不保留失效凭据，内容不变',async()=>{
 const h=await opened();h.tick();h.requests[1].reject({response:{status:409}});await flush();assert.equal(h.requests[2].url,'/business-numbers/reserve')
 h.requests[2].resolve({token:'lease-b',number:'TP-261109-001'});await flush();assert.equal(h.model.orderNo,'TP-261109-001');assert.equal(h.model.projectName,'未保存内容');assert.equal(h.leases.has('lease-a'),false);assert.equal(h.leases.has('lease-b'),true);assert.equal(h.result.error.value,'')
})
test('焦点/联网恢复共用续期请求，退出账号忽略迟到响应',async()=>{
 const h=await opened();h.events.get('focus')();h.events.get('online')();assert.equal(h.requests.length,2)
 h.store.clear();h.events.get('auth-session-clearing')();h.requests[1].resolve({ok:true});await flush();assert.equal(h.leases.size,0);assert.match(h.result.error.value,/账号已退出/);h.unmount();assert.equal(h.timers.size,0);assert.equal(h.documentEvents.size,0)
})
test('重新申请遇到暂时故障后仍会继续重试',async()=>{
 const h=await opened();h.tick();h.requests[1].reject({response:{status:409}});await flush();h.requests[2].reject(Error('数据库繁忙'));await flush();h.tick();assert.equal(h.requests[3].url,'/business-numbers/reserve');h.requests[3].resolve({token:'lease-c',number:'TP-261109-002'});await flush();assert.equal(h.result.error.value,'');assert.equal(h.model.projectName,'未保存内容')
})
