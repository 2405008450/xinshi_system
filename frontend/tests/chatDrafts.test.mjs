import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {computed,effectScope,getCurrentInstance,nextTick,onBeforeUnmount,onScopeDispose,reactive,ref,watch} from 'vue'
import {chatDraftKey,readChatDraft,writeChatDraft,draftFiles,draftImages} from '../src/utils/chatDrafts.js'
const settle=async()=>{await nextTick();await Promise.resolve();await nextTick()}
const source=readFileSync(new URL('../src/composables/useChatDraft.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace('export function','function')
function harness(storage=new Map(),owner='owner',kind='discussion',id='a'){
 const listeners=new Map(),localStorage={getItem:key=>key==='user_id'?owner:storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}
 const api={addEventListener:(key,fn)=>listeners.set(key,fn),removeEventListener:(key)=>listeners.delete(key)}
 const context={computed,getCurrentInstance,nextTick,onBeforeUnmount,onScopeDispose,reactive,ref,watch,chatDraftKey,readChatDraft,writeChatDraft,setTimeout,clearTimeout,localStorage,window:api,document:{...api,visibilityState:'visible'}}
 const factory=runInNewContext(source+';useChatDraft',context)
 const scope=effectScope(),target=ref(id),state=reactive({content:'',mentionIds:[],replyTo:null}),draft=scope.run(()=>factory(computed(()=>[kind,target.value]),()=>({...state}),data=>Object.assign(state,data)))
 return {storage,localStorage,state,draft,target,scope,flush:()=>listeners.get('beforeunload')?.()}
}
test('草稿按账号和会话隔离，切换后恢复文字、@和引用',async()=>{
 const h=harness();await settle();h.state.content='@所有人 待发送';h.state.mentionIds=['__all__'];h.state.replyTo={id:'1'};h.flush()
 h.target.value='b';await settle();assert.equal(h.state.content,'');h.state.content='另一会话';h.state.mentionIds=[];h.state.replyTo=null;h.flush();h.target.value='a';await settle()
 assert.equal(h.state.content,'@所有人 待发送');assert.deepEqual([...h.state.mentionIds],['__all__']);assert.equal(h.state.replyTo.id,'1')
 h.scope.stop();const other=harness(h.storage,'other');await settle();assert.equal(other.state.content,'');other.scope.stop()
})
test('卸载前立即保存，重新打开恢复；发送成功清空后移除草稿',async()=>{
 const h=harness();await settle();h.state.content='切换前尚未触发防抖';h.scope.stop()
 const second=harness(h.storage);await settle();assert.equal(second.state.content,'切换前尚未触发防抖');second.state.content='';second.state.mentionIds=[];second.state.replyTo=null;second.flush();second.scope.stop()
 assert.equal(h.storage.has(chatDraftKey('owner','discussion','a')),false)
})
test('只保存已上传附件引用，不保存未上传文件或失效blob地址',()=>{
 assert.equal(draftFiles([{status:'uploading',file:{name:'pending'}},{status:'ready',data:{id:'file'},file:{name:'ok'}}]).length,1)
 const images=draftImages([{status:'ready',attachment:{id:'image'},file:{name:'图'},url:'blob:old'}]);assert.equal(images[0].url,'');assert.equal(images[0].attachment.id,'image')
})
test('损坏草稿安全忽略，空内容不会留下无效草稿',()=>{
 const h=harness();h.localStorage.setItem('broken','not json');assert.equal(readChatDraft(h.localStorage,'broken'),null);writeChatDraft(h.localStorage,'empty',{content:'',mentionIds:['__all__']});assert.equal(h.storage.has('empty'),false);h.scope.stop()
})


test('同一会话的空白副窗未编辑时，关闭不能覆盖另一窗口草稿',async()=>{
 const shared=new Map(),first=harness(shared),second=harness(shared);await settle();first.state.content='主窗口正在编辑';first.flush();second.scope.stop();assert.equal(readChatDraft(first.localStorage,chatDraftKey('owner','discussion','a')).content,'主窗口正在编辑');first.scope.stop()
})
