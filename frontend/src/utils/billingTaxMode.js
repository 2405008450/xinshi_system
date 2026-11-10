export const billingTaxLabel=mode=>({excl_tax:'不含税',incl_tax:'含税',mixed:'按子订单口径汇总'})[mode]||'待填写金额'
export function billingTaxChoices(order){
  if(order.pricingMode==='fixed')return [['excl_tax',order.adjustedTotal],['incl_tax',order.adjustedTotalInclTax]].filter(([,value])=>value!=null&&value!=='').map(([mode])=>mode)
  return [['excl_tax','adjustedTotal','unitPriceExclTax'],['incl_tax','adjustedTotalInclTax','unitPriceInclTax']].filter(([mode,total,unit])=>(order[total]!=null&&order[total]!=='')||(!Array.isArray(order.prices)&&Object.keys(order[mode==='excl_tax'?'totalsExclTax':'totalsInclTax']||{}).length)||order.prices?.some(price=>price.taxPrices?.[unit]!=null&&price.taxPrices?.[unit]!=='' )).map(([mode])=>mode)
}
export const hasFixedFeeAmount=order=>[order.adjustedTotal,order.adjustedTotalInclTax].some(value=>value!=null&&value!=='')
export function effectiveBillingTaxMode(order){
  const choices=billingTaxChoices(order)
  return choices.length===1?choices[0]:choices.includes(order.billingTaxMode)?order.billingTaxMode:choices.includes(order.effectiveBillingTaxMode)?order.effectiveBillingTaxMode:choices[0]||null
}
