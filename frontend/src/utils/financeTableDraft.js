import {ratePayload} from './customerTranslationRates.js'
import {taxPriceForm,taxUnitAmount} from './taxPrices.js'
import {orderStatementMonth} from './statementRequirementMonth.js'

export const financeDraftFields=['pricingMode','currency','prices','adjustedTotal','adjustedTotalInclTax','billingMonth','explanation','customerExplanation']
export const financePatchKeys={pricingMode:'pricing_mode',currency:'currency',prices:'prices',adjustedTotal:'adjusted_total',adjustedTotalInclTax:'adjusted_total_incl_tax',billingMonth:'billing_month',explanation:'explanation',customerExplanation:'customer_explanation'}
export const copyFinanceValue=value=>JSON.parse(JSON.stringify(value??null))
export function financeDraft(row){
  const prices=(row.prices||[]).map(price=>({...copyFinanceValue(price),taxPrices:taxPriceForm(price.taxPrices),amount:price.amount==null?null:Number(price.amount),unitSize:Number(price.unitSize||1)}))
  return {pricingMode:row.pricingMode||'metric',currency:row.currency||'CNY',prices,adjustedTotal:row.adjustedTotal==null?null:Number(row.adjustedTotal),adjustedTotalInclTax:row.adjustedTotalInclTax==null?null:Number(row.adjustedTotalInclTax),billingMonth:orderStatementMonth(row.orderNo)||row.billingMonth||null,explanation:row.explanation||'',customerExplanation:row.customerExplanation||''}
}
export function financeFieldValue(field,value){
  if(field==='prices')return (value||[]).map(price=>ratePayload({...price,amount:taxUnitAmount(price.taxPrices,price.amount)??null})).map(price=>({...price,amount:price.amount??null,tax_prices:{...price.tax_prices,total_excl_tax:null,total_incl_tax:null}}))
  return value===''&&!['explanation','customerExplanation'].includes(field)?null:value??null
}
export const sameFinanceField=(field,a,b)=>{
  const comparable=value=>field==='prices'?financeFieldValue(field,value).map(({id,...price})=>price):financeFieldValue(field,value)
  return JSON.stringify(comparable(a))===JSON.stringify(comparable(b))
}
