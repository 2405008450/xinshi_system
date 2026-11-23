// 切换只修改财务草稿，保存后再沿用既有接口记录审计。
export async function requestInterpretationPricingModeSwitch(draft,next,confirm){
  if(!draft||!['time','fixed'].includes(next)||draft.settlement.pricing_mode===next)return false
  const target=next==='fixed'?'固定收费':'按时长计费'
  try{if(await confirm(`切换为「${target}」将清空已填写的时长单价、计费数量、加班费、固定收费、调整总价、折扣、结算调整后金额及计费税口径。客户说明、收款记录、账单月份和结算模式保留。确认后需保存才生效，是否继续？`)===false)return false}catch{return false}
  draft.rates=[]
  draft.has_overtime=false
  draft.overtime={amount:undefined,currency:'CNY'}
  draft.adjusted_totals=[]
  draft.fixed_totals=[]
  draft.settlement_adjustments=[]
  draft.settlement.tax_basis='legacy'
  draft.settlement.pricing_mode=next
  return true
}
