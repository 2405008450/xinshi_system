import {savedFieldKey} from './savedDataMerge.js'
const isInterpreters=path=>savedFieldKey(String(path).split('.').at(-1))==='interpreter_assignments'
const read=(row,camel,snake)=>row[camel]??row[snake]
export const savedConflictFieldLabel=path=>isInterpreters(path)?'译员安排':path
export function savedConflictText(path,value){
  if(isInterpreters(path)&&Array.isArray(value)){
    const rows=value.filter(row=>read(row,'translatorId','translator_id')||read(row,'clientSelected','client_selected')||read(row,'customerRating','customer_rating')||read(row,'evaluationNote','evaluation_note'))
    if(!rows.length)return '尚未安排译员'
    const ratings={very_satisfied:'非常满意',satisfied:'满意',basically_satisfied:'基本满意',dissatisfied:'不满意',very_dissatisfied:'非常不满意'}
    return rows.map((row,index)=>{
      const selected=read(row,'translatorId','translator_id'),rating=read(row,'customerRating','customer_rating'),note=read(row,'evaluationNote','evaluation_note')
      return `译员 ${index+1}：${read(row,'translatorLabel','translator_label')||read(row,'translatorName','translator_name')||(selected?'已选择人员':'尚未选择人员')}\n客户选定：${read(row,'clientSelected','client_selected')?'是':'否'}\n客户评价：${ratings[rating]||rating||'未填写'}\n评价/备注：${note||'未填写'}`
    }).join('\n\n')
  }
  return value==null?'（空）':Array.isArray(value)&&!value.length?'未填写':typeof value==='object'?JSON.stringify(value,null,2):String(value)
}
