import {resolveRateQuantity,metricName} from './translationQuantityBasis.js'
import {taxPriceForm} from './taxPrices.js'
import {referenceDraft} from './customerTranslationRates.js'
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
export function fillCustomerReferencePrice(price,references,matrix){
  if(price.referenceId||price.manualReference||price.amount!=null||
    price.taxPrices?.unitPriceExclTax!=null||price.taxPrices?.unitPriceInclTax!=null)return false
  const dimension=price.metric==='customer_auto'
    ?resolveRateQuantity(matrix,price.metric).dimension
    :String(price.metric).startsWith('company_')?'company':'customer'
  const matching=references.filter(reference=>{
    const referenceDimension=String(reference.metric).startsWith('company_')?'company':'customer'
    return dimension===referenceDimension&&priceMatch(reference,price,matrix).matched
  })
  if(matching.length!==1)return false
  const {amount,taxPrices,referenceId,referenceRevision}=referenceDraft(matching[0])
  if(taxPrices.unitPriceExclTax==null&&taxPrices.unitPriceInclTax==null)taxPrices.unitPriceExclTax=amount
  Object.assign(price,{amount,taxPrices,referenceId,referenceRevision})
  return true
}
export function sameCustomerRatePrice(reference,price){
  const amounts=row=>{
    const amount=row.amount==null||row.amount===''?null:Number(row.amount)
    const tax=taxPriceForm(row.taxPrices)
    return [tax.unitPriceExclTax??(tax.unitPriceInclTax==null?amount:null),tax.unitPriceInclTax??null]
  }
  const [refExcl,refIncl]=amounts(reference),[excl,incl]=amounts(price)
  return refExcl===excl&&refIncl===incl
}
export function expectedOrderPrices(prices,languagePair,matrix){
  return prices?.length?prices:String(languagePair||'').split('；').filter(Boolean).map(direction=>({languagePair:direction,metric:'customer_auto',currency:'CNY',unitSize:1}))
}
export function replaceMatchedReference(prices,reference,matrix){
  const index=prices.findIndex(price=>priceMatch(reference,price,matrix).matched)
  if(index<0)throw new Error('所选报价与当前项目的语种、单位、币种或计价数量不匹配，请重新核对')
  return index
}
