const filled=value=>value!=null&&value!==''
export function hasPricingModeData(order){
  if(order.pricingMode==='aggregate')return false
  if(filled(order.adjustedTotal)||filled(order.adjustedTotalInclTax))return true
  return order.pricingMode!=='fixed'&&(order.prices||[]).some(row=>filled(row.taxPrices?.unitPriceExclTax)||filled(row.taxPrices?.unitPriceInclTax)||filled(row.amount))
}
export async function requestPricingModeSwitch(order,next,{confirm,createRate,apply=true,hasChildren=order.hasChildren??!!order.children?.length}){
  const previous=order.pricingMode||'metric'
  if(next===previous||!(hasChildren?['aggregate','fixed']:['metric','fixed']).includes(next))return false
  if(next==='aggregate'){
    try{
      await confirm('切换为子订单汇总后，保存时将清除当前订单的含税和不含税固定收费金额，并按原有子订单价格重新汇总。确认切换？')
    }catch{return false}
    if(apply){
      order.pricingMode='aggregate'
      order.priceAggregate=true
      order.adjustedTotal=undefined
      order.adjustedTotalInclTax=undefined
      order.billingTotals={}
    }
    return true
  }
  if(hasPricingModeData(order)){
    const old=previous==='fixed'?'固定收费':'工作量',target=next==='fixed'?'固定收费':'工作量'
    try{await confirm(`工作量/固定收费，只能选择填写其一。填写了${target}，将自动清除${old}的计价数据，请问是否继续？`)}catch{return false}
  }
  if(apply){
    order.pricingMode=next
    order.priceAggregate=false
    order.prices=next==='fixed'?[]:[createRate(String(order.languagePair||'').split('；')[0]||'')]
    order.adjustedTotal=undefined;order.adjustedTotalInclTax=undefined
    order.billingTaxMode=null;order.effectiveBillingTaxMode=null
    order.totalsExclTax={};order.totalsInclTax={};order.billingTotals={}
  }
  return true
}
