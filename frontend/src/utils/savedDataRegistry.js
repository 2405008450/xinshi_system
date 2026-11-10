import {reactive,ref,markRaw,unref,isRef,isReadonly} from 'vue'
import {copySavedValue,mergeSavedRecord,savedRecords,savedFieldKey,convertSavedLike,isSavedSystemField} from './savedDataMerge'

const sources=new Map(),views=new Map(),conflicts=new WeakMap()
const boundModels=new Map(),bindingByModel=new WeakMap()
export const SAVED_SOURCE=Symbol('saved-data-source')
export const savedConflictRevision=ref(0)
let request,watchResources,started=false,interval,queued,updateTimer,checking=false,revision=0
const pendingResources=new Set()
let activeMetadata=new Set()
const clone=copySavedValue
const skipped=/^\/(?:auth|notifications|saved-data-sync|project-status-sync|health|openapi\.json|chat|discussion-chat|annotation-chat)(?:\/|$)/
const owner=()=>localStorage.getItem('user_id')||''
// setupState包含按需计算的界面属性；隐藏工具尚未初始化时，读取它们可能抛错。
// 同步只收集能安全读取的业务数据，单个展示属性不能中断列表请求。
function readableEntries(value){
  const entries=[]
  for(const [key,descriptor] of Object.entries(Object.getOwnPropertyDescriptors(value))){
    if(!descriptor.enumerable||!('value' in descriptor))continue
    if(isRef(descriptor.value)&&isReadonly(descriptor.value))continue
    try{entries.push([key,value[key]])}catch{}
  }
  return entries
}
function annotate(value,entry,path=[],seen=new WeakSet(),keyStyle='raw'){
  if(!value||typeof value!=='object'||seen.has(value))return value
  seen.add(value)
  try{Object.defineProperty(value,SAVED_SOURCE,{value:markRaw({entry,path,keyStyle}),configurable:true,enumerable:true})}catch{return value}
  if(Array.isArray(value))entry.collections.add({weak:new WeakRef(value),path,keyStyle})
  for(const [key,item] of Object.entries(value))annotate(item,entry,[...path,key],seen,keyStyle)
  return value
}
export function mappedSavedRead(value,source,mapper){
  const meta=source?.[SAVED_SOURCE]
  if(!meta||!value||typeof value!=='object'||value instanceof Promise)return value
  const target=reactive(value),style=/camel/i.test(String(mapper||''))?'camel':meta.keyStyle;annotate(target,meta.entry,meta.path,new WeakSet(),style);meta.entry.results.add(new WeakRef(target));return target
}
// 保留API已有的camelCase等同步转换，同时把来源传递到转换后的响应。
export function savedReadPromise(promise){
  const wrap=base=>({then(ok,fail){return wrap(base.then(value=>{const next=ok?ok(value):value;return mappedSavedRead(next,value,ok)},fail))},catch(fail){return this.then(undefined,fail)},finally(fn){return wrap(base.finally(fn))},[Symbol.toStringTag]:'Promise'})
  return wrap(promise)
}
export function linkSavedCollection(source,value,normalize){
  const meta=source?.[SAVED_SOURCE]
  if(!meta||!Array.isArray(value))return value
  const target=reactive(value);annotate(target,meta.entry,meta.path,new WeakSet(),meta.keyStyle)
  if(normalize){for(const item of meta.entry.collections)if(item.weak.deref()===target)meta.entry.collections.delete(item);meta.entry.collections.add({weak:new WeakRef(target),path:meta.path,prepare:rows=>rows.map(row=>normalize(meta.keyStyle==='camel'?convertSavedLike(row,{projectName:''}):row))})}
  return target
}
function roots(){
  const values=[]
  for(const {instance,active} of views.values()){
    if(!active||instance.isUnmounted)continue
    values.push(instance.setupState)
    if(instance.type?.name==='AppForm')values.push(instance.attrs.model)
  }
  return values
}
function targets(){activeMetadata=new Set();const result=new Map(),seen=new WeakSet();for(const root of roots())collect(root,result,seen,0);for(const binding of boundModels.values()){if(binding.instance.isUnmounted||!binding.instance.vnode.el?.getClientRects?.().length)continue;if(binding.source)activeMetadata.add(binding.source);if(!binding.id)continue;if(!result.has(binding.id))result.set(binding.id,new Set());result.get(binding.id).add(binding.model)}return result}
function collect(value,result,seen,depth){
  try{value=unref(value)}catch{return}
  if(!value||typeof value!=='object'||depth>8||seen.has(value)||value instanceof Element||value instanceof Map||value instanceof Set||value.$el||value.__v_skip||(value.vnode&&value.type&&value.uid!=null))return
  seen.add(value)
  if(value[SAVED_SOURCE])activeMetadata.add(value[SAVED_SOURCE].entry)
  if(Array.isArray(value)){for(const item of value.slice(0,10000))collect(item,result,seen,depth+1);return}
  if(value.id!=null&&value.id!==''){const id=String(value.id);if(!result.has(id))result.set(id,new Set());result.get(id).add(value)}
  for(const [key,item] of readableEntries(value)){if(key.startsWith('$')||key.startsWith('__')||typeof item==='function')continue;collect(item,result,seen,depth+1)}
}
function conflict(target,path,current,latest,before){
  if(isSavedSystemField(path))return
  let changes=conflicts.get(target);if(!changes){changes=new Map();conflicts.set(target,changes)}
  changes.set(path,{path,current:clone(current),latest:clone(latest),before:clone(before)});savedConflictRevision.value++
}
export function modelSavedConflicts(model){savedConflictRevision.value;return [...(conflicts.get(model)?.values()||[])].filter(item=>!isSavedSystemField(item.path))}
export function resolveSavedConflict(model,path,accept){
  const changes=conflicts.get(model),entry=changes?.get(path);if(!entry)return
  if(accept){const parts=path.replace(/\[([^\]]+)\]/g,'.$1').split('.');let target=model;for(const part of parts.slice(0,-1))target=Array.isArray(target)?target.find(item=>String(item.id)===part):target?.[part];if(target)target[parts.at(-1)]=convertSavedLike(clone(entry.latest),target[parts.at(-1)])}
  changes.delete(path);savedConflictRevision.value++
}
function apply(entry,data){
  const old=entry.snapshot,next=clone(data),previous=savedRecords(old),latest=savedRecords(next),current=targets()
  for(const [id,before] of previous){const after=latest.get(id);if(!after)continue;for(const target of current.get(id)||[]){const binding=bindingByModel.get(target);mergeSavedRecord(target,binding?pathValue(before,binding.path):before,binding?pathValue(after,binding.path):after,(path,a,b,c)=>conflict(target,path,a,b,c))}}
  syncViewCollections(old,next)
  for(const item of entry.collections){const target=item.weak.deref();if(!target){entry.collections.delete(item);continue}let before=pathValue(old,item.path),after=pathValue(next,item.path);if(Array.isArray(before)&&Array.isArray(after)){if(item.prepare){before=item.prepare(before);after=item.prepare(after)}else if(item.keyStyle==='camel'){before=before.map(row=>convertSavedLike(row,{projectName:''}));after=after.map(row=>convertSavedLike(row,{projectName:''}))}const holder={items:target};mergeSavedRecord(holder,{items:before},{items:after},(path,a,b,c)=>conflict(target,path,a,b,c));if(holder.items!==target)target.splice(0,target.length,...holder.items)}}
  for(const binding of boundModels.values())if(binding.source===entry&&!binding.instance.isUnmounted&&binding.instance.vnode.el?.getClientRects?.().length)mergeSavedRecord(binding.model,pathValue(old,binding.path),pathValue(next,binding.path),(path,a,b,c)=>conflict(binding.model,path,a,b,c))
  for(const weak of entry.results){const target=weak.deref();if(!target){entry.results.delete(weak);continue}if(Array.isArray(target)&&Array.isArray(old)&&Array.isArray(next)){const holder={items:target};mergeSavedRecord(holder,{items:old},{items:next},(path,a,b,c)=>conflict(holder,path,a,b,c));if(holder.items!==target)target.splice(0,target.length,...holder.items)}else mergeSavedRecord(target,old,next,(path,a,b,c)=>conflict(target,path,a,b,c))}
  entry.snapshot=next;entry.records=new Set(latest.keys());entry.last=Date.now()
}

function recordCollections(value,path=[],result=[]){
  if(!value||typeof value!=='object')return result
  if(Array.isArray(value)){if(value.length&&value.every(row=>row&&typeof row==='object'&&row.id!=null))result.push({path,value});return result}
  for(const [key,item] of Object.entries(value))recordCollections(item,[...path,key],result)
  return result
}
function pathValue(value,path){for(const key of path)value=value?.[Object.keys(value||{}).find(name=>savedFieldKey(name)===savedFieldKey(key))];return value}
function syncViewCollections(before,after){
  const lists=recordCollections(before).map(item=>({...item,next:pathValue(after,item.path),ids:JSON.stringify(item.value.map(row=>String(row.id)))})).filter(item=>Array.isArray(item.next))
  if(!lists.length)return
  const seen=new WeakSet()
  function walk(value,depth=0){
    try{value=unref(value)}catch{return}if(!value||typeof value!=='object'||seen.has(value)||depth>7||value instanceof Element||value instanceof Map||value instanceof Set||value.$el||value.__v_skip||(value.vnode&&value.type&&value.uid!=null))return
    seen.add(value)
    if(Array.isArray(value)){
      const ids=value.length&&value.every(row=>row&&typeof row==='object'&&row.id!=null)?JSON.stringify(value.map(row=>String(row.id))):null
      const source=ids&&lists.find(item=>item.ids===ids)
      if(source){const holder={items:value};mergeSavedRecord(holder,{items:source.value},{items:source.next},(path,a,b,c)=>conflict(value,path,a,b,c));if(holder.items!==value)value.splice(0,value.length,...holder.items)}
      for(const item of value)walk(item,depth+1)
    }else for(const [,item] of readableEntries(value))if(typeof item!=='function')walk(item,depth+1)
  }
  for(const root of roots())walk(root)
}
export function rememberSavedRead(response){
  const config=response.config||{},data=response.data
  if(String(config.method).toLowerCase()!=='get'||config.savedSyncReplay||config.responseType==='blob'||config.responseType==='arraybuffer'||skipped.test(config.url||'')||!data||typeof data!=='object')return data
  const resources=String(response.headers?.['x-saved-resources']||'__all__').split(',').filter(Boolean)
  const key=JSON.stringify([owner(),config.url,config.params||{}]);let entry=sources.get(key)
  const value=reactive(data)
  if(!entry){entry={url:config.url,params:clone(config.params),paramsSerializer:config.paramsSerializer,resources,snapshot:clone(data),records:new Set(savedRecords(data).keys()),results:new Set(),collections:new Set(),owner:owner(),last:Date.now(),versions:null};sources.set(key,entry)}
  else{apply(entry,data);entry.resources=resources}
  entry.readSeq=(entry.readSeq||0)+1;annotate(value,entry);entry.results.add(new WeakRef(value));entry.last=Date.now()
  schedule();return value
}
function activeSources(){const ids=new Set(targets().keys()),now=Date.now();return [...sources.entries()].flatMap(([key,entry])=>{if(entry.owner!==owner()||now-entry.last>1800000){sources.delete(key);return []}for(const weak of entry.results)if(!weak.deref())entry.results.delete(weak);return activeMetadata.has(entry)||[...entry.records].some(id=>ids.has(id))?[entry]:[]})}
async function refresh(entries){
  const current=revision
  // 限制并发，多个窗口同一查询只读一次。
  for(let start=0;start<entries.length;start+=3){if(document.hidden||current!==revision)return;await Promise.allSettled(entries.slice(start,start+3).map(async entry=>{const seq=entry.readSeq=(entry.readSeq||0)+1;const data=await request({url:entry.url,method:'get',params:entry.params,paramsSerializer:entry.paramsSerializer,savedSyncReplay:true});if(current===revision&&!document.hidden&&seq===entry.readSeq)apply(entry,data)}))}
}
export function savedDataChanged(resources){
  if(!started||document.hidden)return
  for(const name of resources)pendingResources.add(name)
  clearTimeout(updateTimer);updateTimer=setTimeout(()=>{const changed=new Set(pendingResources);pendingResources.clear();const entries=activeSources().filter(entry=>entry.resources.includes('__all__')||entry.resources.some(name=>changed.has(name)));if(entries.length)void refresh(entries)},180)
}
async function check(){
  if(!started||document.hidden||checking)return
  const entries=activeSources(),names=[...new Set(entries.flatMap(entry=>entry.resources))];if(!names.length)return
  checking=true
  try{const {versions}=await request({url:'/saved-data-sync/versions',method:'post',data:{resources:names},savedSyncReplay:true});const changed=entries.filter(entry=>!entry.versions||entry.resources.some(name=>entry.versions[name]!==versions[name]));for(const entry of entries)entry.versions=versions;if(changed.length)await refresh(changed)}catch{/* 离线不清空现有内容；恢复或下次版本检查重试。 */}finally{checking=false}
}
function schedule(){
  if(!started)return
  clearTimeout(queued);queued=setTimeout(()=>{if(document.hidden){watchResources([]);return}const names=[...new Set(activeSources().flatMap(entry=>entry.resources))];watchResources(names.slice(0,500));void check()},200)
}
export function installSavedDataRegistry(app,{send,watch:watcher,onEvent,onResume}){
  request=send;watchResources=watcher;started=true
  app.mixin({mounted(){const instance=this.$;const name=String(instance.type.name||instance.type.__name||'');if(/^(El[A-Z]|Element|Router|Transition|KeepAlive)/.test(name))return;views.set(instance.uid,{instance,active:true});schedule()},activated(){const view=views.get(this.$.uid);if(view){view.active=true;schedule()}},deactivated(){const view=views.get(this.$.uid);if(view){view.active=false;schedule()}},beforeUnmount(){views.delete(this.$.uid)}})
  onEvent(resources=>savedDataChanged(resources));onResume(schedule)
  document.addEventListener('visibilitychange',()=>{revision++;if(document.hidden){clearInterval(interval);interval=null;watchResources([])}else{interval??=setInterval(check,60000);schedule()}})
  interval=setInterval(check,60000)
}

// 旧表单有些将记录ID放在外层。只在明确的关联ID与唯一字段投影同时匹配时绑定，绝不按名称猜记录。
export function bindSavedForm(instance,model){
  if(!model||typeof model!=='object'||Array.isArray(model)||model instanceof Map||model.id)return
  if(boundModels.get(instance.uid)?.model===model)return
  const meta=model[SAVED_SOURCE]
  if(meta){const binding={model,instance,source:meta.entry,path:meta.path,id:String(model.id||'')};boundModels.set(instance.uid,binding);schedule();return}
  const ids=new Set();let parent=instance.parent
  for(let depth=0;parent&&depth<7;parent=parent.parent,depth++){
    for(const source of [parent.props,parent.setupState])for(const [key,value] of readableEntries(source||{}))if(/^(?:id|recordId|projectId|clientId|editId|editingId|editingProjectId|currentProjectId)$/i.test(key)&&typeof unref(value)==='string'&&unref(value))ids.add(unref(value))
  }
  if(!ids.size)return
  const choices=[]
  function compare(value,id,path=[],depth=0){
    if(!value||typeof value!=='object'||Array.isArray(value)||depth>3)return
    const keys=Object.keys(model),fields=Object.keys(value),matching=keys.filter(key=>fields.some(name=>savedFieldKey(name)===savedFieldKey(key)))
    const same=matching.filter(key=>{const remote=fields.find(name=>savedFieldKey(name)===savedFieldKey(key));return JSON.stringify(model[key])===JSON.stringify(value[remote])}).length
    if(matching.length>=3&&same>=3)choices.push({id,path,score:same,model,instance})
    for(const [key,item] of Object.entries(value))if(item&&typeof item==='object'&&!Array.isArray(item))compare(item,id,[...path,key],depth+1)
  }
  for(const entry of [...sources.values()].sort((a,b)=>b.last-a.last))for(const [id,record] of savedRecords(entry.snapshot))if(ids.has(id))compare(record,id)
  choices.sort((a,b)=>b.score-a.score);const chosen=choices[0]
  if(!chosen||choices.some(item=>item.score===chosen.score&&(item.id!==chosen.id||JSON.stringify(item.path)!==JSON.stringify(chosen.path))))return
  boundModels.set(instance.uid,chosen);bindingByModel.set(model,chosen);schedule()
}
export function unbindSavedForm(instance){const binding=boundModels.get(instance.uid);if(binding)bindingByModel.delete(binding.model);boundModels.delete(instance.uid)}
