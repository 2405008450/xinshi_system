import {reactive} from 'vue'
import api from '@/api/index'
import {draftHash,sanitizeDraft,draftStringify} from './autoDraftStore.js'
export const CLOUD_DRAFT_DELAY=3000
export const cloudDraftState=reactive({pending:0,error:'',saving:false})
const slots=new Map()
let timer,running=false,failures=0
let readers=0
const readWaiters=[]
function acquireRead(){return new Promise(resolve=>{if(readers<2){readers++;resolve()}else readWaiters.push(resolve)})}
function releaseRead(){if(readWaiters.length)readWaiters.shift()();else readers--}
const owner=()=>localStorage.getItem('user_id')||localStorage.getItem('user_name')||''
const keyOf=key=>key.length<=220?key:`${draftHash(key)}:${key.slice(0,200)}`
const clearedKey=item=>`xinshi.cloudDraftCleared:${item.user}:${item.namespace}:${item.key}`
function slot(namespace,key){const user=owner(),normalized=keyOf(key),id=JSON.stringify([user,namespace,normalized]);if(!slots.has(id))slots.set(id,{user,namespace,key:normalized,generation:0,revision:null,hash:null,pending:undefined,blocked:false,status:reactive({state:'local',error:'',updatedAt:null})});return slots.get(id)}
export const cloudDraftStatus=(namespace,key)=>slot(namespace,key).status
function updatePending(){cloudDraftState.pending=[...slots.values()].filter(item=>item.pending!==undefined).length}
async function read(item){
 await acquireRead()
 let result
 try{if(owner()!==item.user)throw new Error('账号已切换');result=await api.get('/editor-drafts',{params:{namespace:item.namespace,key:item.key}})}finally{releaseRead()}
 if(owner()!==item.user)throw new Error('账号已切换，草稿保留在原账号')
 if(item.revision!==null&&result.revision<item.revision)return {namespace:item.namespace,key:item.key,payload:item.serverPayload??null,revision:item.revision,updated_at:item.status.updatedAt}
 item.serverPayload=result.payload
 item.revision=result.revision;item.hash=draftStringify(result.payload);item.status.updatedAt=result.updated_at
 return result
}
export async function readCloudDraft(namespace,key){const item=slot(namespace,key);try{let result=await read(item);if(item.blocked){item.pending=undefined;updatePending()}try{const cleared=JSON.parse(localStorage.getItem(clearedKey(item))||'null');if(cleared&&result.payload!==null&&(cleared.revision===null||result.revision<=cleared.revision)){queueCloudDraft(namespace,key,null);result={...result,payload:null}}else if(cleared)localStorage.removeItem(clearedKey(item))}catch{/* 不影响读取。 */}item.blocked=false;item.status.error='';if(item.pending===undefined)item.status.state=result.payload===null?'local':'synced';return result}catch(error){item.status.state='local';item.status.error=error.detail||'云端草稿读取失败，继续保留本机备份';throw error}}
export function queueCloudDraft(namespace,key,value){const item=slot(namespace,key);const payload=sanitizeDraft(value);if(payload===undefined)return;const hash=draftStringify(payload);if(item.pending?.hash===hash||hash===item.hash&&item.pending===undefined)return;item.pending={payload,hash};item.status.state='local';updatePending();if(!timer)timer=setTimeout(()=>void flushCloudDrafts(),CLOUD_DRAFT_DELAY)}
export function clearCloudDraft(namespace,key){const item=slot(namespace,key);try{localStorage.setItem(clearedKey(item),JSON.stringify({revision:item.revision===null?null:item.revision+(item.sending?1:0)}))}catch{/* 正式保存不受浏览器配额影响。 */}queueCloudDraft(namespace,key,null);void flushCloudDrafts()}
export function acknowledgeCloudDraft(namespace,key,revision){const item=slot(namespace,key);item.generation++;item.revision=revision;item.hash='null';item.serverPayload=null;item.pending=undefined;item.blocked=false;item.status.state='synced';item.status.error='';updatePending()}
export async function flushCloudDrafts(){
 clearTimeout(timer);timer=null;if(running)return
 const batch=[...slots.values()].filter(item=>item.user===owner()&&item.pending!==undefined&&!item.blocked).slice(0,20)
 if(!batch.length)return
 running=true;cloudDraftState.saving=true
 try{
  for(const item of batch){
   if(item.revision!==null)continue
   const existing=await read(item)
   if(existing.payload!==null&&item.pending.payload!==null&&draftStringify(existing.payload)!==item.pending.hash){item.blocked=true;item.status.state='conflict';item.status.error='云端已有另一份草稿，本机内容已保留；请重新打开表单读取云端版本';throw new Error(item.status.error)}
  }
  const writes=batch.map(item=>({item,pending:item.pending,revision:item.revision,generation:item.generation}))
  writes.forEach(({item})=>{item.status.state='saving';item.sending=true})
  const result=await api.post('/editor-drafts/batch',{drafts:writes.map(({item,pending,revision})=>({namespace:item.namespace,key:item.key,revision,payload:pending.payload}))})
  for(const {item,pending,generation} of writes){
   if(item.generation!==generation)continue
   const saved=result.find(value=>value.namespace===item.namespace&&value.key===item.key)
   if(!saved||saved.conflict){item.blocked=true;item.status.state='conflict';item.status.error='另一窗口已更新此草稿，本机内容保留，未覆盖云端版本';cloudDraftState.error=item.status.error;continue}
   item.revision=saved.revision;item.hash=pending.hash;item.serverPayload=pending.payload;item.status.updatedAt=saved.updated_at;item.status.error=''
   if(pending.payload===null)try{localStorage.removeItem(clearedKey(item))}catch{/* 之后读取时仍可核对清除版本。 */}
   if(item.pending===pending){item.pending=undefined;item.status.state='synced'}else item.status.state='local'
  }
  if(!batch.some(item=>item.blocked))cloudDraftState.error=''
  failures=0
 }catch(error){failures++;cloudDraftState.error=error.detail||error.message||'云端草稿同步失败，本机备份保留';batch.forEach(item=>{if(!item.blocked){item.status.state='local';item.status.error=cloudDraftState.error}})}
 finally{batch.forEach(item=>{item.sending=false});running=false;cloudDraftState.saving=false;updatePending();if(!timer&&[...slots.values()].some(item=>item.user===owner()&&item.pending!==undefined&&!item.blocked))timer=setTimeout(()=>void flushCloudDrafts(),failures?Math.min(30000,CLOUD_DRAFT_DELAY*2**Math.min(failures,4))+Math.random()*500:CLOUD_DRAFT_DELAY)}
}
if(typeof window!=='undefined'){
 window.addEventListener('online',()=>void flushCloudDrafts())
 window.addEventListener('auth-session-clearing',()=>void flushCloudDrafts())
 document.addEventListener('visibilitychange',()=>{if(document.hidden)void flushCloudDrafts()})
}
