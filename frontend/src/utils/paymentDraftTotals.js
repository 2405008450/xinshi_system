import {effectiveBillingTaxMode} from './billingTaxMode.js'

export function paymentDraftTotals(order,calculated){
  const filled=value=>value!=null&&value!==''
  const currency=order.currency||order.prices?.[0]?.currency||'CNY'
  const excl=order.pricingMode==='fixed'?{}:{...calculated.excl.totals}
  const incl=order.pricingMode==='fixed'?{}:{...calculated.incl.totals}
  if(filled(order.adjustedTotal))excl[currency]=Number(order.adjustedTotal).toFixed(2)
  if(filled(order.adjustedTotalInclTax))incl[currency]=Number(order.adjustedTotalInclTax).toFixed(2)
  const mode=effectiveBillingTaxMode(order)
  const items=[]
  for(const [key,label,totals] of [['billing','计费总价',mode==='incl_tax'?incl:excl],['excl','不含税总价',excl],['incl','含税总价',incl]]){
    for(const [currency,amount] of Object.entries(totals))items.push({key:`${key}:${currency}`,label,currency,amount:Number(amount).toFixed(2),taxMode:key==='billing'?mode:key==='incl'?'incl_tax':'excl_tax'})
  }
  return items
}
