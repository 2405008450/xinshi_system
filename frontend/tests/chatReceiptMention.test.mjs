import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
const source=readFileSync(new URL('../src/components/chat/ChatConversation.vue',import.meta.url),'utf8')
const fragment=source.slice(source.indexOf('async function acknowledge(message)'),source.indexOf('async function recall(message)'))
function harness(fail=false){
 const seenMentions={value:['earlier-read']};let refreshes=0, errors=0
 const run=runInNewContext(fragment+';acknowledge',{seenMentions,refreshSessions:()=>{refreshes++},acknowledgeProjectChatMessage:async()=>{if(fail)throw Error('failed');return {isAcknowledged:true}},unacknowledgeProjectChatMessage:async()=>({isAcknowledged:false}),ElMessage:{error:()=>errors++},detail:e=>e.message})
 return {run,seenMentions,refreshes:()=>refreshes,errors:()=>errors}
}
test('收到成功只消除该条未读标记并刷新目录，取消确认不恢复未读',async()=>{
 const h=harness(),message={id:'target',isAcknowledged:false}
 await h.run(message);assert.deepEqual([...h.seenMentions.value],['earlier-read','target']);assert.equal(h.refreshes(),1)
 await h.run(message);assert.deepEqual([...h.seenMentions.value],['earlier-read','target']);assert.equal(message.isAcknowledged,false)
})
test('收到请求失败保留提醒和原确认状态',async()=>{
 const h=harness(true),message={id:'target',isAcknowledged:false}
 await h.run(message);assert.deepEqual([...h.seenMentions.value],['earlier-read']);assert.equal(message.isAcknowledged,false);assert.equal(h.refreshes(),0);assert.equal(h.errors(),1)
})
