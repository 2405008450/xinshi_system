import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source=readFileSync(new URL('../src/components/chat/ChatFavoriteRecovery.vue',import.meta.url),'utf8')
const script=source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm,'')
function model(request){
  const events=[]
  const instance=runInNewContext(script+';({load,restore,restoreAll,selected,failures,page,items,total,error})',{
    ref:value=>({value}),defineModel:()=>({value:true}),defineEmits:()=>event=>events.push(event),watch:()=>{},onBeforeUnmount:()=>{},
    annotationChatRequest:request,AbortController,ElMessage:{success:()=>{}},
  })
  return {...instance,events}
}
test('部分失败保留失败项勾选并刷新列表，成功项通知收藏夹更新',async()=>{
  const state=model(async(_,endpoint)=>endpoint==='restore-favorites'?{restored:['a'],failed:[{projectId:'b',reason:'无权限'}]}:{total:1,items:[{projectId:'b',orderNo:'B'}]})
  state.selected.value=['a','b']
  await state.restore(state.selected.value)
  assert.deepEqual(Array.from(state.selected.value),['b'])
  assert.equal(state.failures.value[0].reason,'无权限')
  assert.deepEqual(state.events,['restored'])
  assert.equal(state.items.value[0].projectId,'b')
})
test('一键恢复从第一页取最多十个，超过十个的请求不发送',async()=>{
  const requests=[]
  const state=model(async(_,endpoint,options)=>{
    requests.push({endpoint,options})
    if(endpoint==='restore-favorites')return {restored:options.data.projectIds,failed:[]}
    return {total:15,items:Array.from({length:10},(_,i)=>({projectId:String(i),orderNo:String(i)}))}
  })
  await state.restore(Array.from({length:11},(_,i)=>String(i)))
  assert.equal(requests.length,0)
  state.page.value=2;state.items.value=[{projectId:'wrong-page'}]
  await state.restoreAll()
  assert.equal(requests[0].options.params.offset,0)
  assert.equal(requests.find(row=>row.endpoint==='restore-favorites').options.data.projectIds.length,10)
  assert.equal(requests.find(row=>row.endpoint==='restore-favorites').options.data.projectIds.includes('wrong-page'),false)
})
test('恢复列表加载失败时不发送一键恢复请求',async()=>{
  let posted=false
  const state=model(async(_,endpoint)=>{if(endpoint==='restore-favorites')posted=true;throw new Error('网络失败')})
  state.page.value=2
  await state.restoreAll()
  assert.equal(posted,false)
  assert.equal(state.error.value,'网络失败')
})
