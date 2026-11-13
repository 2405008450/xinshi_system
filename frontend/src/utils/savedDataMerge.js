import {taxPriceForm} from './taxPrices.js'

const plain=value=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype
export const savedFieldKey=key=>key.replace(/([a-z0-9])([A-Z])/g,'$1_$2').toLowerCase()
export const isSavedSystemField=key=>['updated_at','created_at'].includes(savedFieldKey(String(key).split('.').at(-1)))
const normalize=value=>Array.isArray(value)?value.map(normalize):plain(value)?Object.fromEntries(Object.entries(value).map(([key,item])=>[savedFieldKey(key),normalize(item)]).sort(([a],[b])=>a.localeCompare(b))):value
export const sameSavedValue=(a,b)=>{
  if(typeof a==='number'&&typeof b==='string'&&/^-?\d+(?:\.\d+)?$/.test(b))return a===Number(b)
  if(typeof b==='number'&&typeof a==='string')return sameSavedValue(b,a)
  return JSON.stringify(normalize(a))===JSON.stringify(normalize(b))
}
export const copySavedValue=value=>value===undefined?undefined:JSON.parse(JSON.stringify(value))
const keyIn=(obj,key)=>Object.keys(obj).find(name=>savedFieldKey(name)===savedFieldKey(key))
const idOf=item=>plain(item)&&item.id!=null?String(item.id):null
const rateValue=(row,key)=>row[keyIn(row,key)]
const rateNumber=value=>value==null||value===''?null:Number(value)
function orderRateValues(rows){
  if(!Array.isArray(rows)||!rows.every(row=>plain(row)&&typeof rateValue(row,'language_pair')==='string'&&'metric' in row))return null
  return rows.map(row=>{
    const tax=taxPriceForm(rateValue(row,'tax_prices'))
    return {
      languagePair:rateValue(row,'language_pair'),
      currency:row.currency||'CNY',
      metric:row.metric,
      unitSize:rateNumber(rateValue(row,'unit_size'))||1,
      amount:tax.unitPriceExclTax??rateNumber(row.amount),
      tax,
      referenceId:rateValue(row,'reference_id')||null,
      referenceRevision:rateNumber(rateValue(row,'reference_revision')),
    }
  })
}
function sameOrderRates(a,b){
  const left=orderRateValues(a),right=orderRateValues(b)
  return left!==null&&right!==null&&sameSavedValue(left,right)
}
function edited(value,before){
  if(plain(value)&&plain(before))return Object.entries(before).some(([key,item])=>{const local=keyIn(value,key);return !isSavedSystemField(key)&&local!=null&&edited(value[local],item)})
  if(Array.isArray(value)&&Array.isArray(before))return value.length!==before.length||value.some((item,index)=>edited(item,before[index]))
  return !sameSavedValue(value,before)
}
function convertLike(value,example){
  if(typeof example==='number'&&typeof value==='string'&&/^-?\d+(?:\.\d+)?$/.test(value))return Number(value)
  if(Array.isArray(value))return value.map(item=>convertLike(item,example?.[0]))
  if(!plain(value))return value
  const camel=example&&Object.keys(example).some(key=>/[a-z][A-Z]/.test(key))
  return Object.fromEntries(Object.entries(value).map(([key,item])=>[keyIn(example||{},key)||(camel?key.replace(/_([a-z])/g,(_,c)=>c.toUpperCase()):key),convertLike(item,example?.[keyIn(example||{},key)])]))
}
export const convertSavedLike=convertLike
export function mergeSavedRecord(target,before,after,conflict=()=>{},path=''){
  if(!plain(target)||!plain(before)||!plain(after))return
  for(const [serverKey,next] of Object.entries(after)){
    const oldKey=keyIn(before,serverKey),key=keyIn(target,serverKey)
    // 系统时间不属于用户输入；统一采用服务端值，格式变化也不产生编辑冲突。
    if(key!=null&&isSavedSystemField(serverKey)){target[key]=convertLike(next,target[key]);continue}
    if(key==null||oldKey==null||sameSavedValue(before[oldKey],next))continue
    const old=before[oldKey],current=target[key],field=path?`${path}.${key}`:key
    if(sameSavedValue(current,next))continue
    // A draft rate can lack a database ID, and the API adds calculated quantities.
    // Compare the editable rate values before asking the user to resolve a whole-list conflict.
    const orderPrices=serverKey==='prices'
    const report=()=>{
      if(orderPrices&&(sameOrderRates(current,next)||sameOrderRates(old,next)))return
      conflict(field,current,next,old)
    }
    if(Array.isArray(current)&&Array.isArray(old)&&Array.isArray(next)&&[...old,...next].every(item=>idOf(item)!=null)){
      const oldIds=old.map(idOf),currentIds=current.map(idOf),newById=new Map(next.map(item=>[idOf(item),item])),oldById=new Map(old.map(item=>[idOf(item),item]))
      for(const row of current){const id=idOf(row);if(oldById.has(id)&&newById.has(id))mergeSavedRecord(row,oldById.get(id),newById.get(id),conflict,`${field}[${id}]`)}
      if(JSON.stringify(currentIds)===JSON.stringify(oldIds)){
        const currentById=new Map(current.map(item=>[idOf(item),item]))
        const removedDirty=current.filter(item=>!newById.has(idOf(item))&&
          !(orderPrices&&sameOrderRates([item],[oldById.get(idOf(item))]))&&edited(item,oldById.get(idOf(item))))
        if(removedDirty.length){report();continue}
        current.splice(0,current.length,...next.map(item=>currentById.get(idOf(item))||convertLike(item,current[0])))
      }else if(JSON.stringify(next.map(idOf))!==JSON.stringify(oldIds))report()
    }else if(plain(current)&&plain(old)&&plain(next))mergeSavedRecord(current,old,next,conflict,field)
    else if(sameSavedValue(current,old))target[key]=convertLike(next,current)
    else if(orderPrices&&sameOrderRates(current,old)){
      if(!sameOrderRates(current,next))target[key]=convertLike(next,current)
    }else report()
  }
}
export function savedRecords(value,result=new Map(),seen=new WeakSet()){
  if(!value||typeof value!=='object'||seen.has(value))return result
  seen.add(value)
  if(Array.isArray(value)){for(const item of value)savedRecords(item,result,seen);return result}
  if(!plain(value))return result
  const id=idOf(value);if(id)result.set(id,value)
  for(const item of Object.values(value))savedRecords(item,result,seen)
  return result
}
