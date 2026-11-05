import {resolveRateQuantity,metricName} from './translationQuantityBasis.js'
export function pricingUnit(mode,matrix,reference=false){
  if(mode==='customer_auto')return reference?null:resolveRateQuantity(matrix,mode).metric||null
  return String(mode||'').replace(/^customer_auto:/,'').replace(/^company_/,'')||null
}
export function priceMatch(reference,price,matrix){
  const reasons=[]
  if(reference.languagePair!==price.languagePair)reasons.push('语种方向不同')
  const left=pricingUnit(reference.metric,null,true),right=pricingUnit(price.metric,matrix)
  if(!left)reasons.push('客户报价尚未明确计量单位')
  else if(!right)reasons.push('项目尚未明确计量单位')
  else if(left!==right)reasons.push(`单位不同（${metricName(left)}／${metricName(right)}）`)
  if((reference.currency||'CNY')!==(price.currency||'CNY'))reasons.push('币种不同')
  if(Number(reference.unitSize||1)!==Number(price.unitSize||1))reasons.push('单价对应数量不同')
  return {matched:!reasons.length,reasons}
}
export function expectedOrderPrices(prices,languagePair,matrix){
  return prices?.length?prices:String(languagePair||'').split('；').filter(Boolean).map(direction=>({languagePair:direction,metric:'customer_auto',currency:'CNY',unitSize:1}))
}
export function replaceMatchedReference(prices,reference,matrix){
  const index=prices.findIndex(price=>priceMatch(reference,price,matrix).matched)
  if(index<0)throw new Error('所选报价与当前项目的语种、单位、币种或计价数量不匹配，请重新核对')
  return index
}
