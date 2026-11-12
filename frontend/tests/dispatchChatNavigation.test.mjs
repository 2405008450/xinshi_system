import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
const source=readFileSync(new URL('../src/views/resource/components/ResourceRequestDispatchDialog.vue',import.meta.url),'utf8')
const enter=source.slice(source.indexOf('async function enterChat()'),source.indexOf('const executionForm'))
function harness(load){
 const opens=[], errors={value:''},props={batchId:'batch'},state={canEnterChat:{value:true},busy:{value:false},loading:{value:false},projectTarget:{value:{sourceType:'annotation',projectId:'target'}},orderNo:{value:'AP-TARGET'},props,sequence:1,error:errors,getAnnotationProject:load,getProject:load,closeDetails:()=>{},emit:()=>{},nextTick:async()=>{},dock:{openChat:session=>opens.push(session)}}
 const run=runInNewContext(enter+';enterChat',state)
 return {run,opens,errors,props}
}
test('需求通知只打开经过身份和订单号核对的项目',async()=>{
 const h=harness(async()=>({id:'target',orderNo:'AP-TARGET',projectName:'目标项目'}))
 await h.run();assert.equal(h.opens.length,1);assert.equal(h.opens[0].projectId,'target');assert.equal(h.opens[0].subtitle,'AP-TARGET')
})
test('关联ID返回其他订单时留在通知中报错，不能打开错误项目',async()=>{
 const h=harness(async()=>({id:'target',orderNo:'AP-WRONG'}));await h.run()
 assert.equal(h.opens.length,0);assert.match(h.errors.value,/订单号/)
})
test('切换需求通知后旧项目响应不能触发跳转',async()=>{
 let resolve;const h=harness(()=>new Promise(done=>resolve=done));const pending=h.run();h.props.batchId='other'
 resolve({id:'target',orderNo:'AP-TARGET'});await pending;assert.equal(h.opens.length,0)
})
