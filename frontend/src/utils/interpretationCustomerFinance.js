import {taxPriceForm,taxPricePayload,taxPriceSummary} from './taxPrices.js'
import {quotationLineCents,quotationMoney} from './quotation.js'
export const interpretationUnits = ['月','周','天','半天','小时']
export const interpretationCurrencies = ['CNY','USD','EUR','HKD','GBP','JPY','KRW','AUD','CAD','SGD']
export const emptyInterpretationFinance = () => ({
  rates: [], has_overtime: false, overtime: null, adjusted_totals: [], fixed_totals: [], explanation: '',
  settlement: {billing_month:null,tax_basis:'legacy',pricing_mode:'time',payment_method:'individual',quotation_required:false,
    invoice_required:false,customer_explanation:'',payment_note:'',payment_status:'unrecorded',payments:[]},
})

export function interpretationFinancePayload(draft){
  const money = ({taxPrices,tax_prices,...row}) => ({...row,tax_prices:taxPricePayload(taxPrices)})
  return {
    ...draft,
    settlement:{...draft.settlement,payments:draft.settlement.payments.map(row=>({...row,received_on:row.received_on||null})),billing_month:draft.settlement.billing_month||null},
    rates:draft.rates.map(money),
    adjusted_totals:draft.adjusted_totals.map(money),
    fixed_totals:draft.fixed_totals.map(money),
    overtime:draft.has_overtime ? money(draft.overtime) : null,
  }
}

export function interpretationLineTotal(row,basis,automatic=false){
  const included=basis==='incl_tax'
  if (basis!=='legacy'&&!automatic){
    const override=included?row.taxPrices?.totalInclTax:row.taxPrices?.totalExclTax
    if(override!=null)return quotationLineCents({quantity:1,unit_price:override},6)
  }
  const unit=basis==='legacy'?row.amount:included?row.taxPrices?.unitPriceInclTax:row.taxPrices?.unitPriceExclTax
  return quotationLineCents({quantity:row.quantity,unit_price:unit},6)
}

export function interpretationFinanceTotals(draft,basis=draft?.settlement.tax_basis,automatic=false){
  if(!draft)return {}
  const result={}
  function add(code, cents){
    if(cents!=null)result[code]=(result[code]??0n)+cents
  }
  const toCents=amount=>quotationLineCents({quantity:1,unit_price:amount},6)
  const taxTotal=row=>basis==='incl_tax'?row.taxPrices?.totalInclTax:row.taxPrices?.totalExclTax
  const fixed=draft.settlement.pricing_mode==='fixed'
  for(const row of fixed?[]:draft.rates)add(row.currency,interpretationLineTotal(row,basis))
  if(!fixed&&draft.has_overtime){
    const row=draft.overtime
    add(row.currency,toCents(basis==='legacy'?row.amount:taxTotal(row)))
  }
  for(const row of fixed?draft.fixed_totals:automatic?[]:draft.adjusted_totals){
    const cents=toCents(basis==='legacy'?row.amount:taxTotal(row))
    if(cents!=null)result[row.currency]=cents
  }
  return Object.fromEntries(Object.entries(result).map(([code,cents])=>[code,quotationMoney(cents)]))
}
export function interpretationUnitPrice(row){
  return taxPriceSummary(row.taxPrices||row.tax_prices,row.currency,row.unit,false)
    || (row.amount!=null ? `原单价（税口径未确认）：${row.currency} ${row.amount}/${row.unit}` : '待填写单价')
}

export function interpretationWorkload(row){
  if(row.quantity==null)return '待填写工作量'
  const hours=['天','半天'].includes(row.unit) && row.hours!=null ? `（每${row.unit} ${row.hours} 小时${row.includes_lunch?'，含午餐':''}）` : ''
  return `${row.quantity} ${row.unit}${hours}`
}

export function financeSummary(data={}){
  const rates=(data.rates||[]).map(row=>{
    const totals=taxPriceSummary(row.taxPrices||row.tax_prices,row.currency).split('\n').filter(line=>line.includes('总价：'))
    return [row.direction,interpretationUnitPrice(row),`工作量：${interpretationWorkload(row)}`,...totals].join('\n')
  })
  if(data.has_overtime&&data.overtime)rates.push(taxPriceSummary(data.overtime.taxPrices||data.overtime.tax_prices,data.overtime.currency)||`原加班费（税口径未确认）：${data.overtime.currency} ${data.overtime.amount}`)
  for(const row of data.adjusted_totals||[])rates.push(taxPriceSummary(row.taxPrices||row.tax_prices,row.currency)||`原调整总价（税口径未确认）：${row.currency} ${row.amount}`)
  for(const row of data.fixed_totals||[])rates.push(`固定收费：${taxPriceSummary(row.taxPrices||row.tax_prices,row.currency)||row.currency+' '+row.amount}`)
  if(data.invoice){
    const labels={unissued:'未开票',partial:'部分开票',issued:'已开票'}
    rates.push(`发票状态：${labels[data.invoice.invoice_status]||'未开票'}`)
  }
  if(data.explanation)rates.push(`说明：${data.explanation}`)
  return rates.join('\n')||'未设置'
}
export const formatFinanceAmounts=data=>Object.entries(data||{}).map(([code,amount])=>`${code} ${amount}`).join('\n')||'待设置'
export function financeDraft(data){
  const defaults=emptyInterpretationFinance()
  const draft=JSON.parse(JSON.stringify({...defaults,...data,settlement:{...defaults.settlement,...data?.settlement}}))
  if(draft.settlement.payment_method==='statement')draft.settlement.payment_method='monthly'
  for(const row of draft.rates){row.taxPrices=taxPriceForm(row.tax_prices||row.taxPrices);row.amount=Number(row.amount);row.quantity=Number(row.quantity);row.hours=row.hours==null?null:Number(row.hours)}
  draft.overtime=draft.overtime?{...draft.overtime,taxPrices:taxPriceForm(draft.overtime.tax_prices),amount:Number(draft.overtime.amount)}:{amount:undefined,currency:'CNY'}
  draft.adjusted_totals=draft.adjusted_totals.map(row=>({...row,taxPrices:taxPriceForm(row.tax_prices),amount:Number(row.amount)}))
  draft.fixed_totals=draft.fixed_totals.map(row=>({...row,taxPrices:taxPriceForm(row.tax_prices),amount:Number(row.amount)}))
  draft.settlement.payments=draft.settlement.payments.map(row=>({...row,amount:row.amount==null?undefined:Number(row.amount)}))
  return draft
}
