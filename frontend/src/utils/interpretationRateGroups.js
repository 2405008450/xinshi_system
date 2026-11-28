import {taxPriceForm} from './taxPrices.js'
import {quotationLineCents} from './quotation.js'

const present=value=>value!=null&&value!==''&&Number.isFinite(Number(value))
export function hasRateContent(row={}){
 return present(row.amount)||Object.values(taxPriceForm(row.taxPrices||row.tax_prices)).some(present)
}
export function hasOvertimeContent(row){
 if(!row)return false
 if(row.pricing_mode==='rates')return (row.rates||[]).some(hasRateContent)
 if(row.pricing_mode==='multiplier')return present(row.multiplier)&&present(row.quantity)
 return hasRateContent(row)
}
export function meaningfulRates(rows){return (rows||[]).filter(hasRateContent)}
export function groupRates(rows=[]){
 const groups=new Map()
 rows.forEach((rate,index)=>{const key=rate.direction||'';if(!groups.has(key))groups.set(key,{key,direction:key,rows:[]});groups.get(key).rows.push({rate,index})})
 return [...groups.values()]
}
function applyAdjustments(totals,adjustments,basis){
 const prefix=basis==='incl_tax'?'incl':basis==='excl_tax'?'excl':'legacy'
 for(const row of adjustments||[]){
  if(present(row[prefix+'_amount']))totals[row.currency]=quotationLineCents({quantity:1,unit_price:row[prefix+'_amount']},6)
  else if(present(row[prefix+'_discount'])&&totals[row.currency]!=null)totals[row.currency]=(totals[row.currency]*BigInt(row[prefix+'_discount'])+50n)/100n
 }
 return totals
}
export function rateGroupTotals(rows,basis,adjust=true){
 const totals={}
 for(const row of rows){
  const tax=taxPriceForm(row.taxPrices||row.tax_prices),override=basis==='incl_tax'?tax.totalInclTax:tax.totalExclTax
  const unit=basis==='legacy'?row.amount:basis==='incl_tax'?tax.unitPriceInclTax:tax.unitPriceExclTax
  const value=basis!=='legacy'&&present(override)?quotationLineCents({quantity:1,unit_price:override},6):quotationLineCents({quantity:row.quantity,unit_price:unit},6)
  if(value!=null)totals[row.currency]=(totals[row.currency]??0n)+value
 }
 return adjust?applyAdjustments(totals,rows[0]?.group_adjustments,basis):totals
}
export function combinedRateTotals(rows,basis,adjust=true){
 const totals={}
 for(const group of groupRates(rows))for(const [currency,amount] of Object.entries(rateGroupTotals(group.rows.map(item=>item.rate),basis)))totals[currency]=(totals[currency]??0n)+amount
 return adjust?applyAdjustments(totals,rows[0]?.combined_adjustments,basis):totals
}
