import {meaningfulRates} from './interpretationRateGroups.js'
import {taxPriceSummary} from './taxPrices.js'
import {savedFieldKey} from './savedDataMerge.js'
import {formatBusinessDateTimeMinute} from './dateTime.js'
const isInterpreters=path=>savedFieldKey(String(path).split('.').at(-1))==='interpreter_assignments'
const isTimeRanges=path=>savedFieldKey(String(path).split('.').at(-1))==='time_ranges'
const read=(row,camel,snake)=>row[camel]??row[snake]
export const savedConflictFieldLabel=path=>isInterpreters(path)?'译员安排':isTimeRanges(path)?'时间段':String(path).endsWith('rates')?'组合单价':path
export function savedConflictText(path,value){
  if(String(path).endsWith('rates')&&Array.isArray(value)){const rows=meaningfulRates(value);return rows.length?rows.map((row,index)=>`单价 ${index+1}：${row.direction||'未选择方向'}\n${taxPriceSummary(row.taxPrices||row.tax_prices,row.currency,row.unit)||'单价：'+row.currency+' '+row.amount+'/'+row.unit}\n工作量：${row.quantity??'未填写'} ${row.unit}`).join('\n\n'):'未填写单价'}
  if(isTimeRanges(path)&&Array.isArray(value)){
    if(!value.length)return '尚未填写时间段'
    return value.map((row,index)=>{
      const details=read(row,'locationDetails','location_details')
      const locations=details?.length?details.map(location=>[read(location,'countryProvince','country_province'),location.city,location.address].filter(Boolean).join(' ')):row.locations||[]
      const directions=read(row,'languageDirections','language_directions')||[]
      return `时间段 ${index+1}\n预定开始：${formatBusinessDateTimeMinute(read(row,'scheduledStart','scheduled_start'))}\n预定结束：${formatBusinessDateTimeMinute(read(row,'scheduledEnd','scheduled_end'))}\n实际开始：${formatBusinessDateTimeMinute(read(row,'actualStart','actual_start'))}\n实际结束：${formatBusinessDateTimeMinute(read(row,'actualEnd','actual_end'))}\n项目地点：${locations.filter(Boolean).join('；')||'未填写'}\n口译方向：${directions.map((direction,n)=>`${direction.display||(read(direction,'languageLabels','language_labels')||[]).join(' ↔ ')||'方向 '+(n+1)}（${read(direction,'requiredCount','required_count')??'未填'}人）`).join('；')||'未填写'}`
    }).join('\n\n')
  }
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
