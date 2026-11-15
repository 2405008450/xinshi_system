export function isMatchableOrder(order,currency){
  const totals=order.billingTotals||{}
  return !order.incomplete&&!order.fixedPricingFrom&&
    (currency?Object.hasOwn(totals,currency):Object.keys(totals).length>0)
}

export function collectMatchTotals(orders,ids){
  const cents={}
  function visit(nodes){
    for(const order of nodes){
      if(ids.has(order.id)){
        for(const [currency,amount] of Object.entries(order.billingTotals||{})){
          cents[currency]=(cents[currency]||0)+Math.round(Number(amount)*100)
        }
      }else{
        visit(order.children||[])
      }
    }
  }
  visit(orders)
  return Object.fromEntries(Object.entries(cents).map(([currency,value])=>[currency,(value/100).toFixed(2)]))
}

export function formatMatchTotals(totals){
  return Object.entries(totals||{}).map(([currency,amount])=>`${currency} ${Number(amount).toFixed(2)}`).join('\n')||'—'
}
