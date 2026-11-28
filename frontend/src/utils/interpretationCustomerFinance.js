import {combinedRateTotals,meaningfulRates,hasOvertimeContent} from './interpretationRateGroups.js'
import {taxPriceForm,taxPricePayload,taxPriceSummary} from './taxPrices.js'
import {quotationLineCents,quotationMoney} from './quotation.js'
import {businessPaymentForm,businessPaymentPayload,legacyBusinessPaymentRegistration} from './businessFinancePayment.js'
export const interpretationUnits = ['月','周','天','半天','小时']
export const interpretationCurrencies = ['CNY','USD','EUR','HKD','GBP','JPY','KRW','AUD','CAD','SGD']
export const emptyInterpretationFinance = () => ({
  rates: [], has_overtime: false, overtime: null, adjusted_totals: [], fixed_totals: [], settlement_adjustments:[], explanation: '',
  settlement: {billing_month:null,tax_basis:'legacy',pricing_mode:'time',payment_method:'individual',quotation_required:false,
    invoice_required:false,customer_explanation:'',payment_note:'',payment_status:'unrecorded',payments:[]},
})

export function interpretationFinancePayload(draft){
  const {paymentConfirmation,paymentDraft,paymentLegacyFullReceivedOn,...fields}=draft
  const money = ({taxPrices,tax_prices,...row}) => ({...row,tax_prices:taxPricePayload(taxPrices)})
  return {
    ...fields,
    has_overtime:!!draft.has_overtime&&hasOvertimeContent(draft.overtime),
    ...(paymentConfirmation?{payment_registration:businessPaymentPayload(draft)}:{}),
    settlement:{...draft.settlement,payments:draft.settlement.payments.map(row=>({...row,received_on:row.received_on||null})),billing_month:draft.settlement.billing_month||null},
    rates:meaningfulRates(draft.rates).map(money),
    adjusted_totals:draft.adjusted_totals.map(money),
    fixed_totals:draft.fixed_totals.map(money),
    overtime:draft.has_overtime&&hasOvertimeContent(draft.overtime) ? {...money(draft.overtime),amount:draft.overtime.pricing_mode&&draft.overtime.pricing_mode!=='total'?0:draft.overtime.amount,rates:meaningfulRates(draft.overtime.rates).map(money)} : null,
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

export function interpretationOvertimeRates(draft){
 const row=draft?.overtime
 if(!draft?.has_overtime||!row||!row.pricing_mode||row.pricing_mode==='total')return []
 if(row.pricing_mode==='rates')return row.rates||[]
 const base=draft.rates?.[row.base_rate_index||0]
 if(!base)return []
 const multiplier=Number(row.multiplier??1),prices=taxPriceForm(base.taxPrices||base.tax_prices)
 return [{...base,group_adjustments:[],combined_adjustments:[],amount:Number(base.amount||0)*multiplier,quantity:Number(row.quantity??1),taxPrices:{...prices,totalExclTax:null,totalInclTax:null,unitPriceExclTax:prices.unitPriceExclTax==null?null:prices.unitPriceExclTax*multiplier,unitPriceInclTax:prices.unitPriceInclTax==null?null:prices.unitPriceInclTax*multiplier}}]
}

export function interpretationFinanceTotals(draft,basis=draft?.settlement.tax_basis,automatic=false,final=true){
  if(!draft)return {}
  const result={}
  function add(code, cents){
    if(cents!=null)result[code]=(result[code]??0n)+cents
  }
  const toCents=amount=>quotationLineCents({quantity:1,unit_price:amount},6)
  const taxTotal=row=>basis==='incl_tax'?row.taxPrices?.totalInclTax:row.taxPrices?.totalExclTax
  const fixed=draft.settlement.pricing_mode==='fixed'
  if(!fixed)for(const rows of [draft.rates,interpretationOvertimeRates(draft)])for(const [currency,value] of Object.entries(combinedRateTotals(rows,basis)))add(currency,value)
  if(!fixed&&draft.has_overtime&&(!draft.overtime.pricing_mode||draft.overtime.pricing_mode==='total')){
    const row=draft.overtime
    add(row.currency,toCents(basis==='legacy'?row.amount:taxTotal(row)))
  }
  for(const row of fixed?draft.fixed_totals:automatic?[]:draft.adjusted_totals){
    const cents=toCents(basis==='legacy'?row.amount:taxTotal(row))
    if(cents!=null)result[row.currency]=cents
  }
  if(!automatic&&final){
    const prefix=basis==='incl_tax'?'incl':basis==='excl_tax'?'excl':'legacy'
    for(const row of draft.settlement_adjustments||[]){
      const manual=row[prefix+'_amount'],discount=row[prefix+'_discount']
      if(manual!=null&&manual!=='')addFinal(row.currency,toCents(manual))
      else if(discount!=null&&result[row.currency]!=null)addFinal(row.currency,(result[row.currency]*BigInt(discount)+50n)/100n)
    }
  }
  function addFinal(currency,value){if(value!=null)result[currency]=value}
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
  if(data.has_overtime&&data.overtime){
    const overtimeRates=interpretationOvertimeRates(data)
    if((data.overtime.pricing_mode||'total')==='total')rates.push(taxPriceSummary(data.overtime.taxPrices||data.overtime.tax_prices,data.overtime.currency)||`原加班费（税口径未确认）：${data.overtime.currency} ${data.overtime.amount}`)
    else for(const row of overtimeRates)rates.push(`加班费：${row.direction}\n${interpretationUnitPrice(row)}\n工作量：${interpretationWorkload(row)}`)
  }
  for(const row of data.adjusted_totals||[])rates.push(taxPriceSummary(row.taxPrices||row.tax_prices,row.currency)||`原调整总价（税口径未确认）：${row.currency} ${row.amount}`)
  for(const row of data.fixed_totals||[])rates.push(`固定收费：${taxPriceSummary(row.taxPrices||row.tax_prices,row.currency)||row.currency+' '+row.amount}`)
  for(const row of data.settlement_adjustments||[])rates.push(`结算调整 ${row.currency}：${['excl','incl','legacy'].flatMap((key,index)=>[row[key+'_discount']!=null?['不含税','含税','税口径未确认'][index]+'折扣 '+row[key+'_discount']+'%':'',row[key+'_amount']!=null?'调整后金额 '+row[key+'_amount']:'']).filter(Boolean).join('；')}`)
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
  for(const row of draft.rates){row.taxPrices=taxPriceForm(row.taxPrices||row.tax_prices);row.amount=Number(row.amount);row.quantity=Number(row.quantity);row.hours=row.hours==null?null:Number(row.hours)}
  draft.overtime=draft.overtime?{...draft.overtime,taxPrices:taxPriceForm(draft.overtime.taxPrices||draft.overtime.tax_prices),amount:Number(draft.overtime.amount)}:{amount:undefined,currency:'CNY'}
  draft.overtime.rates=(draft.overtime.rates||[]).map(row=>({...row,amount:Number(row.amount),quantity:row.quantity==null?undefined:Number(row.quantity),hours:row.hours==null?null:Number(row.hours),taxPrices:taxPriceForm(row.taxPrices||row.tax_prices)}))
  draft.adjusted_totals=draft.adjusted_totals.map(row=>({...row,taxPrices:taxPriceForm(row.taxPrices||row.tax_prices),amount:Number(row.amount)}))
  draft.fixed_totals=draft.fixed_totals.map(row=>({...row,taxPrices:taxPriceForm(row.taxPrices||row.tax_prices),amount:Number(row.amount)}))
  draft.settlement.payments=draft.settlement.payments.map(row=>({...row,amount:row.amount==null?undefined:Number(row.amount)}))
  for(const row of draft.settlement_adjustments||[])for(const key of Object.keys(row))if(key!=='currency'&&row[key]!=null)row[key]=Number(row[key])
  if(draft.settlement.pricing_mode!=='fixed'&&draft.adjusted_totals.length){
    // 旧版手工总价合并到同一调整入口，按原最终金额转换，避免丢失历史折扣效果。
    const bases=[['excl','excl_tax','totalExclTax'],['incl','incl_tax','totalInclTax'],['legacy','legacy',null]]
    const totals=Object.fromEntries(bases.map(([key,basis])=>[key,interpretationFinanceTotals(draft,basis)]))
    for(const old of draft.adjusted_totals){
      let target=draft.settlement_adjustments.find(row=>row.currency===old.currency)
      if(!target){target={currency:old.currency};draft.settlement_adjustments.push(target)}
      for(const [key,,field] of bases)if((field?old.taxPrices?.[field]:old.amount)!=null&&target[key+'_amount']==null&&totals[key][old.currency]!=null)target[key+'_amount']=Number(totals[key][old.currency])
    }
    draft.adjusted_totals=[]
  }
  Object.assign(draft,businessPaymentForm(legacyBusinessPaymentRegistration(draft)))
  if(draft.paymentConfirmation.isPaid&&(draft.paymentConfirmation.paymentOption==='full'||draft.paymentConfirmation.fullPaymentSource==='details')){
    const code=draft.paymentConfirmation.fullPaymentCurrency||'CNY'
    if(interpretationFinanceTotals(draft)[code]!=null)draft.paymentConfirmation.fullPaymentTotalKey=`billing:${code}`
  }
  if(draft.paymentConfirmation.isPaid&&draft.paymentConfirmation.paymentOption==='deposit'){
    if(!draft.paymentDraft.length)draft.paymentDraft.push({stage_type:'deposit',stage_no:1,currency:draft.paymentConfirmation.fullPaymentCurrency||'CNY',planned_amount:undefined,actual_amount:undefined,payment_time:null,payment_method:draft.paymentConfirmation.paymentAccount||'',proofs:draft.paymentConfirmation.proofs||'',matched_order_ids:[],confirmed_by_name:null,confirmed_at:null})
    if(!draft.paymentDraft[0].payment_method)draft.paymentDraft[0].payment_method=draft.paymentConfirmation.paymentAccount||''
  }
  return draft
}
