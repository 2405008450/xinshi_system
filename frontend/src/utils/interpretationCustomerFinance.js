import {taxPriceForm,taxPriceSummary} from './taxPrices.js'
export function financeSummary(data={}){
  const rates=(data.rates||[]).map(row=>`${row.direction}：${taxPriceSummary(row.taxPrices||row.tax_prices,row.currency,row.unit)||('原单价（税口径未确认） '+row.currency+' '+row.amount+'/'+row.unit)} × ${row.quantity}${['天','半天'].includes(row.unit)?`（${row.hours}小时${row.includes_lunch?'，含中午/午餐时间':''}）`:''}`)
  if(data.has_overtime&&data.overtime)rates.push(taxPriceSummary(data.overtime.taxPrices||data.overtime.tax_prices,data.overtime.currency)||`原加班费（税口径未确认）：${data.overtime.currency} ${data.overtime.amount}`)
  for(const row of data.adjusted_totals||[])rates.push(taxPriceSummary(row.taxPrices||row.tax_prices,row.currency)||`原调整总价（税口径未确认）：${row.currency} ${row.amount}`)
  if(data.explanation)rates.push(`说明：${data.explanation}`)
  return rates.join('\n')||'未设置'
}
export const formatFinanceAmounts=data=>Object.entries(data||{}).map(([code,amount])=>`${code} ${amount}`).join('\n')||'待设置'
export function financeDraft(data){
  const draft=JSON.parse(JSON.stringify(data))
  for(const row of draft.rates){row.taxPrices=taxPriceForm(row.tax_prices||row.taxPrices);row.amount=Number(row.amount);row.quantity=Number(row.quantity);row.hours=row.hours==null?null:Number(row.hours)}
  draft.overtime=draft.overtime?{...draft.overtime,taxPrices:taxPriceForm(draft.overtime.tax_prices),amount:Number(draft.overtime.amount)}:{amount:undefined,currency:'CNY'}
  draft.adjusted_totals=draft.adjusted_totals.map(row=>({...row,taxPrices:taxPriceForm(row.tax_prices),amount:Number(row.amount)}))
  return draft
}
