export function financeSummary(data={}){
  const rates=(data.rates||[]).map(row=>`${row.direction}：${row.currency} ${row.amount}/${row.unit} × ${row.quantity}${['天','半天'].includes(row.unit)?`（${row.hours}小时${row.includes_lunch?'，含中午/午餐时间':''}）`:''}`)
  if(data.has_overtime&&data.overtime)rates.push(`总加班费：${data.overtime.currency} ${data.overtime.amount}`)
  for(const row of data.adjusted_totals||[])rates.push(`调整后总价：${row.currency} ${row.amount}`)
  if(data.explanation)rates.push(`说明：${data.explanation}`)
  return rates.join('\n')||'未设置'
}
export const formatFinanceAmounts=data=>Object.entries(data||{}).map(([code,amount])=>`${code} ${amount}`).join('\n')||'待设置'
export function financeDraft(data){
  const draft=JSON.parse(JSON.stringify(data))
  for(const row of draft.rates){row.amount=Number(row.amount);row.quantity=Number(row.quantity);row.hours=row.hours==null?null:Number(row.hours)}
  draft.overtime=draft.overtime?{...draft.overtime,amount:Number(draft.overtime.amount)}:{amount:undefined,currency:'CNY'}
  draft.adjusted_totals=draft.adjusted_totals.map(row=>({...row,amount:Number(row.amount)}))
  return draft
}
