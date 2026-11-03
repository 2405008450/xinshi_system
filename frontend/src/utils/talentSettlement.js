export const settlementCategoryOptions = [{value:'interpretation',label:'口译'},{value:'written_translation',label:'笔译'},{value:'annotation',label:'标注'},{value:'collection',label:'采集'}]
export const settlementCurrencyOptions = [{value:'CNY',label:'CNY 人民币'},{value:'USD',label:'USD 美元'},{value:'HKD',label:'HKD 港币'},{value:'EUR',label:'EUR 欧元'},{value:'GBP',label:'GBP 英镑'},{value:'BRL',label:'BRL 巴西雷亚尔'},{value:'IDR',label:'IDR 印尼盾'}]
// 原有 word/thousand_words 保持“字”语义；新“词”使用独立键，避免改写历史计价口径。
export const settlementUnitOptions = [{value:'character',label:'字（字符）'},{value:'per_word',label:'词'},{value:'source_word',label:'源文词'},{value:'target_word',label:'译文词'},{value:'per_thousand_words',label:'千词'},{value:'word',label:'字（原有口径）'},{value:'thousand_words',label:'千字（原有口径）'},{value:'hour',label:'小时'},{value:'work_hour',label:'工作小时'},{value:'effective_hour',label:'有效小时'},{value:'day',label:'天'},{value:'month',label:'月'},{value:'occurrence',label:'次'},{value:'item',label:'条'},{value:'second',label:'秒'},{value:'minute',label:'分钟'},{value:'page',label:'页'},{value:'image',label:'张'},{value:'project',label:'项目'}]
export const settlementServiceOptions = [{value:'translation',label:'翻译'},{value:'proofreading',label:'校对'},{value:'editing',label:'编辑'},{value:'lqa',label:'LQA'}]
export const settlementStatusOptions = [{value:'pending',label:'待核对'},{value:'confirmed',label:'已确认'}]
export const settlementPriceTypeOptions = [{value:'fixed',label:'固定价'},{value:'range',label:'区间价'},{value:'negotiable',label:'可协商'}]
export const settlementLabel = (options,value) => options.find(item=>item.value===value)?.label || value || '-'
export const emptySettlement = () => ({revision:0,bankAccount:'',paypalAccount:'',payoneerAccount:'',wechatPaymentCode:'',alipayPaymentCode:'',invoiceAvailable:null,invoiceEntity:'',gigPlatformCalculation:false,prices:[]})
export const settlementForm = value => ({...emptySettlement(),...(value||{}),prices:(value?.prices||[]).map(row=>({
  status:'confirmed',priceType:'fixed',serviceType:null,amountMax:null,languagePair:'',rawText:'',sourceFile:'',sourceSheet:'',sourceRow:null,sourceColumn:'',notes:'',
  ...row,amount:row.amount==null?null:Number(row.amount),amountMax:row.amountMax==null?null:Number(row.amountMax),
  currency:row.currency===undefined&&row.status===undefined?'CNY':row.currency??null,
}))})
export const newSettlementPrice = () => ({id:crypto.randomUUID(),category:null,amount:null,amountMax:null,unit:'',currency:null,status:'pending',priceType:'fixed',serviceType:null,languagePair:'',rawText:'',sourceFile:'',sourceSheet:'',sourceRow:null,sourceColumn:'',notes:''})
export const settlementPriceAmount = row => {
  const amount=row.amount==null?'-':String(row.amount)
  if(row.priceType==='range')return `${amount} ～ ${row.amountMax==null?'-':row.amountMax}`
  if(row.priceType==='negotiable')return row.amount==null?'可协商':`${amount}（可协商）`
  return amount
}
export const settlementPriceSource = row => [row.sourceFile,row.sourceSheet,row.sourceRow==null?'':`第 ${row.sourceRow} 行`,row.sourceColumn].filter(Boolean).join(' / ') || '-'
