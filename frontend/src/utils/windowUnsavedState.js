import {hasOvertimeContent} from './interpretationRateGroups.js'
import { ref, toRaw, watch } from 'vue'
import { savedFieldKey, sameSavedFieldValue } from './savedDataMerge'

// 正式保存基线独立于草稿：写入本机/云端草稿不消除未保存标记。
export const windowUnsavedRevision = ref(0)
const models = new Map(), forms = new Map()
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value))
const identity = model => model && typeof model === 'object' ? toRaw(model) : null
const owner = () => localStorage.getItem('user_id') || localStorage.getItem('user_name') || ''
const pathParts = path => (Array.isArray(path) ? path : String(path).replace(/\[([^\]]+)\]/g, '.$1').split('.')).map(String)
const valueAt = (model,path) => pathParts(path).reduce((value,key)=>value?.[key],model)
const ignored = key => /^(?:id|updatedAt|updated_at|createdAt|created_at|orderNo|order_no|clientCode|client_code|revision|expectedUpdatedAt|expected_updated_at)$/.test(key)
const bump = () => windowUnsavedRevision.value++
const emptyInput=value=>value==null||typeof value==='string'&&!value.trim()||Array.isArray(value)&&value.every(emptyInput)
const sameUnsavedValue=(path,a,b)=>(emptyInput(a)&&emptyInput(b))||sameSavedFieldValue(path,a,b)
const hasTouched=(entry,path)=>[...entry.touched].some(item=>item==='*'||item===path||item.startsWith(path+'.')||path.startsWith(item+'.'))
function baselineAtInteraction(entry,path,value){
  if(hasTouched(entry,path))return
  const parts=pathParts(path);let target=entry.baseline
  for(const part of parts.slice(0,-1)){if(!target[part]||typeof target[part]!=='object')target[part]={};target=target[part]}
  target[parts.at(-1)]=copy(value)
}

function entryFor(model) {
  const key=identity(model)
  if(!key)return null
  let entry=models.get(key)
  if(!entry){
    entry={model,baseline:copy(model),managed:false,active:true,creating:!model.id,touched:new Set(),generation:0,owner:owner(),users:new Set()}
    entry.stop=watch(model,()=>{
      if(entry.pendingSnapshot){
        const before=entry.pendingSnapshot;entry.pendingSnapshot=null
        for(const key of Object.keys(model))if(!ignored(key)&&!sameUnsavedValue(key,before[key],model[key])){baselineAtInteraction(entry,key,before[key]);entry.touched.add(key)}
      }
      bump()
    },{deep:true,flush:'sync'})
    models.set(key,entry)
  }
  return entry
}

export function beginUnsavedModel(model,baseline,{creating=false,root}={}) {
  const entry=entryFor(model);if(!entry)return
  entry.touched.clear();entry.pendingSnapshot=null;entry.managed=true;entry.active=true;entry.creating=creating;entry.baseline=copy(baseline);entry.root=root;entry.generation++;entry.owner=owner();bump()
}
export function pauseUnsavedModel(model){const entry=models.get(identity(model));if(entry){entry.active=false;entry.generation++;bump()}}
export function acknowledgeUnsavedModel(model){const entry=models.get(identity(model));if(entry){entry.baseline=copy(model);entry.touched.clear();entry.pendingSnapshot=null;entry.creating=false;bump()}}
export function forgetUnsavedModel(model){const key=identity(model),entry=models.get(key);if(entry&&!entry.users.size){entry.stop();models.delete(key);bump()}else if(entry){entry.managed=false;entry.active=false;bump()}}

export function bindUnsavedForm(instance,model,{root,fields,excluded}) {
  const previous=forms.get(instance.uid)
  if(previous?.entry.model===model)return
  unbindUnsavedForm(instance)
  const entry=entryFor(model);if(!entry)return
  const binding={entry,root,fields,excluded};forms.set(instance.uid,binding);entry.users.add(instance.uid);bump()
}
export function unbindUnsavedForm(instance){
  const binding=forms.get(instance.uid);if(!binding)return
  const entry=binding.entry;entry.users.delete(instance.uid);forms.delete(instance.uid)
  if(!entry.managed&&!entry.users.size){entry.stop();models.delete(identity(entry.model))}
  bump()
}
export function touchUnsavedForm(instance,event){
  const binding=forms.get(instance.uid);if(!binding||binding.excluded())return
  const entry=binding.entry
  const field=binding.fields().find(field=>field.$el?.contains(event.target))
  if(field?.prop){const path=pathParts(field.prop).join('.');baselineAtInteraction(entry,path,valueAt(entry.model,path));entry.touched.add(path)}
  else {
    // 远程下拉的选项位于表单外，等模型真正变化后再识别本次操作修改的字段。
    if(event.target?.closest?.('button,input:not([readonly]):not([disabled]),textarea:not([readonly]):not([disabled]),select,.el-select,.el-checkbox,.el-radio'))entry.pendingSnapshot=copy(entry.model)
  }
  bump()
}
export function resetUnmanagedWindow(root,preserveTouched=false){
  if(!root)return
  for(const binding of forms.values()){
    const entry=binding.entry
    if(!entry.managed&&(!preserveTouched||!entry.touched.size)&&binding.root()?.closest('.el-dialog')===root){entry.baseline=copy(entry.model);entry.touched.clear();entry.owner=owner();entry.generation++}
  }
  bump()
}

function differences(entry,fields,root){
  const result=[],covered=new Set()
  for(const field of fields){
    if(!field.prop||!field.$el)continue
    const path=pathParts(field.prop).join('.'),key=pathParts(path)[0]
    if(ignored(key))continue
    if(['rates','overtime'].includes(key)&&sameSavedFieldValue(key,entry.model[key],entry.baseline[key]))continue
    if(['has_overtime','hasOvertime'].includes(key)&&!hasOvertimeContent(entry.model.overtime)&&!hasOvertimeContent(entry.baseline.overtime))continue
    covered.add(key)
    if(!entry.touched.has('*')&&![...entry.touched].some(item=>item===path||item.startsWith(path+'.')||path.startsWith(item+'.')))continue
    if(sameUnsavedValue(path,valueAt(entry.model,path),valueAt(entry.baseline,path)))continue
    result.push({entry,path,target:field.$el,label:field.label||field.$el.getAttribute?.('data-dialog-field-search-label')||field.$el.querySelector('.el-form-item__label')?.textContent?.trim()||'未保存字段'})
  }
  const remaining=Object.keys(entry.model).filter(key=>!ignored(key)&&(!['has_overtime','hasOvertime'].includes(key)||hasOvertimeContent(entry.model.overtime)||hasOvertimeContent(entry.baseline.overtime))&&(!covered.has(key)||entry.touched.has(key)&&!result.some(item=>item.path===key||item.path.startsWith(key+'.')))&&
    (entry.touched.has('*')||[...entry.touched].some(path=>path===key||path.startsWith(key+'.')))&&!sameUnsavedValue(key,entry.model[key],entry.baseline?.[key]))
  // 复合编辑器可能不使用el-form-item，仍保留可定位的分区入口。
  if(remaining.length){
    const section=root.matches('[data-unsaved-section]')?root:root.querySelector('[data-unsaved-section]')||root
    for(const key of remaining){
      const target=section.querySelector(`[data-unsaved-field="${CSS.escape(key)}"]`)
      if(target)result.push({entry,path:key,target,label:target.getAttribute('data-unsaved-label')||key})
    }
    const unmapped=remaining.filter(key=>!result.some(item=>item.path===key))
    if(unmapped.length)result.push({entry,path:unmapped.join(','),target:section,label:section.getAttribute('data-unsaved-section')||'其他未保存内容'})
  }
  return result
}

export function windowUnsavedItems(root){
  windowUnsavedRevision.value
  if(!root)return []
  const result=[],bound=new Set()
  for(const binding of forms.values()){
    const element=binding.root(),entry=binding.entry
    if(!element?.isConnected||element.closest('.el-dialog')!==root||binding.excluded()||!entry.active||entry.owner!==owner())continue
    bound.add(entry);result.push(...differences(entry,binding.fields(),element))
  }
  for(const entry of models.values()){
    if(bound.has(entry)||!entry.managed||!entry.active||entry.owner!==owner())continue
    const element=entry.root?.()
    if(element?.nodeType===1&&element.isConnected&&element.closest('.el-dialog')===root)result.push(...differences(entry,[],element))
  }
  return result.filter((item,index,items)=>items.findIndex(other=>other.entry===item.entry&&other.path===item.path)===index)
}

function matchKeys(value,key){return value&&typeof value==='object'?Object.keys(value).find(name=>savedFieldKey(name)===savedFieldKey(key)):undefined}
// 小窗中的独立字段保存，只确认该请求实际提交的字段；失败、草稿和上传不更新基线。
export function captureUnsavedSave(config){
  if(!['post','put','patch'].includes(String(config.method).toLowerCase())||/editor-drafts|upload|screenshot|\/files|auth|notification|\/chat|conversation|\/preview|\/search|\/count|sync|lease/i.test(config.url||''))return null
  let data=config.data
  if(typeof data==='string'){try{data=JSON.parse(data)}catch{return null}}
  if(!data||typeof data!=='object'||data instanceof FormData||Array.isArray(data))return null
  const records=[]
  for(const entry of models.values()){
    if(!entry.active||entry.owner!==owner()||!entry.model.id)continue
    const id=String(entry.model.id)
    if(!String(config.url||'').split(/[/?]/).includes(id)&&String(data.id||data.project_id||data.projectId||'')!==id)continue
    const values=[]
    for(const key of Object.keys(entry.model)){
      if(ignored(key))continue
      const remote=matchKeys(data,key)
      if(remote&&sameSavedFieldValue(key,entry.model[key],data[remote]))values.push([key,copy(entry.model[key])])
    }
    if(values.length)records.push({entry,generation:entry.generation,values,owner:entry.owner})
  }
  return records
}
export function completeUnsavedSave(records,response){
  if(response?.success===false||response?.saved===false)return
  for(const {entry,generation,values,owner:actor} of records||[]){
    if(!entry.active||entry.generation!==generation||actor!==owner())continue
    for(const [key,value] of values)entry.baseline[key]=value
  }
  if(records?.length)bump()
}

export function unsavedDraftState(model){
 const entry=models.get(identity(model))
 return entry?{paths:[...entry.touched]}:null
}
export function restoreUnsavedDraftState(model,state){
 const entry=models.get(identity(model));if(!entry||!Array.isArray(state?.paths))return
 for(const path of state.paths)if(typeof path==='string'&&path!=='*'&&!ignored(pathParts(path)[0]))entry.touched.add(path)
 bump()
}
