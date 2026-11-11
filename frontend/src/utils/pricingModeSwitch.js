const filled=value=>value!=null&&value!==''
export function hasPricingModeData(order){
  if(filled(order.adjustedTotal)||filled(order.adjustedTotalInclTax))return true
  return order.pricingMode!=='fixed'&&(order.prices||[]).some(row=>filled(row.taxPrices?.unitPriceExclTax)||filled(row.taxPrices?.unitPriceInclTax)||filled(row.amount))
}
export async function requestPricingModeSwitch(order,next,{confirm,createRate,apply=true}){
  const previous=order.pricingMode||'metric'
  if(!['metric','fixed'].includes(next)||next===previous)return false
  if(hasPricingModeData(order)){
    const old=previous==='fixed'?'固定收费':'工作量',target=next==='fixed'?'固定收费':'工作量'
    try{await confirm(`工作量/固定收费，只能选择填写其一。填写了${target}，将自动清除${old}的计价数据，请问是否继续？`)}catch{return false}
  }
  if(apply){
    order.pricingMode=next
    order.prices=next==='fixed'?[]:[createRate(String(order.languagePair||'').split('；')[0]||'')]
    order.adjustedTotal=undefined;order.adjustedTotalInclTax=undefined
    order.billingTaxMode=null;order.effectiveBillingTaxMode=null
    order.totalsExclTax={};order.totalsInclTax={};order.billingTotals={}
  }
  return true
}
