import {normalizeWordCountMatrix,WORD_COUNT_METRICS} from './wordCountMatrix.js'
import {calculateCustomerPrice} from './translationCustomerFinance.js'
export const quantityBasisOptions=[{value:'customer_auto',label:'自动选择（客户优先，无则我司）'},{value:'company_characters_no_spaces',label:'我司统计（字符数（不计空格））'},{value:'company_words',label:'我司统计（字数）'},{value:'company_cjk_chars_korean_words',label:'我司统计（中朝）'},{value:'company_foreign_words',label:'我司统计（外文）'},{value:'company_documents',label:'我司统计（份数）'},{value:'company_pages',label:'我司统计（页数）'}]
export const metricName=key=>WORD_COUNT_METRICS.find(row=>row.key===key)?.label||key
export function basisLabel(mode){if(String(mode).startsWith('customer_auto')){const metric=String(mode).split(':')[1];return metric?`客户统计（${metricName(metric)}）`:'自动选择（客户优先，无则我司）'}return quantityBasisOptions.find(row=>row.value===mode)?.label||`历史客户口径（${metricName(mode)}）`}
export function resolvedBasisLabel(mode,{dimension,metric}={}){
  if(mode!=='customer_auto'||!metric)return basisLabel(mode)
  return `${dimension==='company'?'我司统计':'客户统计'}（${metricName(metric)}）`
}
export function customerQuantityChoices(matrix){const values=normalizeWordCountMatrix(matrix).customer;return WORD_COUNT_METRICS.filter(row=>values[row.key]!=null).map(row=>({...row,value:values[row.key]}))}
export function projectQuantityChoices(matrix){
  const values=normalizeWordCountMatrix(matrix)
  return [['customer','客户统计'],['company','我司统计']].flatMap(([dimension,label])=>WORD_COUNT_METRICS
    .filter(metric=>values[dimension][metric.key]!=null)
    .map(metric=>({value:dimension==='customer'?`customer_auto:${metric.key}`:`company_${metric.key}`,label:`${label} · ${metric.label}：${values[dimension][metric.key]}`,quantity:values[dimension][metric.key]})))
}
export function validQuantityBasis(mode){
  return mode==='customer_auto'||WORD_COUNT_METRICS.some(({key})=>[key,`customer_auto:${key}`,`company_${key}`].includes(mode))
}
export function rateQuantityOptions(matrix,current){
  const normalized=normalizeWordCountMatrix(matrix)
  const options=[{value:'customer_auto',label:'自动选择（客户优先，无则我司）'}]
  for(const [dimension,label] of [['customer','客户统计'],['company','我司统计']]){
    for(const metric of WORD_COUNT_METRICS){
      const count=normalized[dimension][metric.key]
      options.push({value:dimension==='customer'?`customer_auto:${metric.key}`:`company_${metric.key}`,label:`${label} · ${metric.label}${matrix?`：${count??'待补录'}`:''}`})
    }
  }
  if(WORD_COUNT_METRICS.some(({key})=>key===current))options.push({value:current,label:basisLabel(current)})
  return options
}
export function resolveRateQuantity(matrix,mode){
  const normalized=normalizeWordCountMatrix(matrix)
  if(String(mode).startsWith('customer_auto')){
    const choices=customerQuantityChoices(matrix)
    const selected=String(mode).split(':')[1]
    if(selected){const quantity=normalized.customer[selected];return {quantity,metric:selected,error:quantity==null?'未登记对应数量':null}}
    if(choices.length===1)return {quantity:choices[0].value,metric:choices[0].key,dimension:'customer'}
    if(!choices.length){const own=WORD_COUNT_METRICS.filter(({key})=>normalized.company[key]!=null);if(own.length===1)return {quantity:normalized.company[own[0].key],metric:own[0].key,dimension:'company'};return {quantity:null,error:own.length?'我司统计有多栏，请选择统计口径':'客户统计和我司统计均未填写，请先登记数量和单位'}}
    return {quantity:null,error:choices.length?'客户统计有多栏，请选择统计口径':'未登记客户统计'}
  }
  const company=String(mode).startsWith('company_'),metric=company?String(mode).slice(8):mode
  const quantity=normalized[company?'company':'customer'][metric]
  return {quantity,error:quantity==null?'未登记对应数量':null,metric}
}
const signature=price=>`${price.languagePair}|${price.currency}|${price.metric}|${Number(price.unitSize||1)}`
export function calculateOrderPriceTree(order,originalPrices=order.prices||[]){
  const totals=new Map();let incomplete=false
  function visit(node,newPrices,oldPrices){
    const children=node.children||[]
    if(children.length){for(const child of children){const before=child.prices||[],oldMap=new Map(oldPrices.map(row=>[signature(row),Number(row.amount)]));const inherits=!before.length||before.every(row=>oldMap.has(signature(row))&&oldMap.get(signature(row))===Number(row.amount));const choices=String(child.languagePair||node.languagePair||'').split('；');const current=inherits?newPrices.filter(row=>!child.languagePair||choices.includes(row.languagePair)):before;visit(child,current,before)};return}
    if(!newPrices.length)incomplete=true
    for(const price of newPrices){const {quantity}=resolveRateQuantity(node.wordCountMatrix,price.metric);const amount=calculateCustomerPrice(price.amount,quantity,price.unitSize||1);if(amount==null){incomplete=true;continue}const cents=BigInt(amount.replace('.',''));totals.set(price.currency||'CNY',(totals.get(price.currency||'CNY')||0n)+cents)}
  }
  visit(order,order.prices||[],originalPrices)
  return {totals:Object.fromEntries([...totals].map(([currency,cents])=>[currency,`${cents/100n}.${String(cents%100n).padStart(2,'0')}`])),incomplete}
}

export function calculateTaxOrderPriceTree(order,originalPrices=order.prices||[]){
  function price(row,key){return {...row,amount:row.taxPrices?.[key]??row.tax_prices?.[key.replace(/[A-Z]/g,letter=>'_'+letter.toLowerCase())]??null}}
  function node(row,key){return {...row,prices:(row.prices||[]).map(item=>price(item,key)),children:(row.children||[]).map(item=>node(item,key))}}
  return Object.fromEntries([['excl','unitPriceExclTax'],['incl','unitPriceInclTax']].map(([kind,key])=>[kind,calculateOrderPriceTree(node(order,key),originalPrices.map(item=>price(item,key)))]))
}
