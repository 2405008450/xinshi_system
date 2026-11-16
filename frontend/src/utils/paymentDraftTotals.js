import {effectiveBillingTaxMode} from './billingTaxMode.js'

export function paymentDraftTotals(order,calculated){
  const filled=value=>value!=null&&value!==''
  const currency=order.currency||order.prices?.[0]?.currency||'CNY'
  const excl=order.pricingMode==='fixed'?{}:{...calculated.excl.totals}
  const incl=order.pricingMode==='fixed'?{}:{...calculated.incl.totals}
  for(const [totals,base,discount,manual] of [
    [excl,order.adjustedTotal,order.discountExcl,order.totalAdjustmentExcl],
    [incl,order.adjustedTotalInclTax,order.discountIncl,order.totalAdjustmentIncl],
  ]){
    const target=order.totalAdjustment?.currency||currency
    if(filled(base))totals[currency]=Number(base).toFixed(2)
    if(filled(manual))totals[target]=Number(manual).toFixed(2)
    else if((order.pricingMode==='fixed'||!filled(base))&&filled(discount)&&filled(totals[target])){
      const cents=Math.round(Number(totals[target])*100)
      totals[target]=(Math.round(cents*discount/100)/100).toFixed(2)
    }
  }
  const mode=effectiveBillingTaxMode(order)
  const items=[]
  for(const [key,label,totals] of [['billing','计费总价',mode==='incl_tax'?incl:excl],['excl','不含税总价',excl],['incl','含税总价',incl]]){
    for(const [currency,amount] of Object.entries(totals))items.push({key:`${key}:${currency}`,label,currency,amount:Number(amount).toFixed(2),taxMode:key==='billing'?mode:key==='incl'?'incl_tax':'excl_tax'})
  }
  return items
}
