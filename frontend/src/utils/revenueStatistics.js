export const revenuePeriods = [
  {value:'week',label:'周'}, {value:'month',label:'月'},
  {value:'quarter',label:'季度'}, {value:'year',label:'年'},
]
export const revenueBases = [
  {value:'billing',label:'项目计费口径'},
  {value:'excl',label:'不含税总价'}, {value:'incl',label:'含税总价'},
]
export const rankShortcuts = [{label:'1–10名',min:1,max:10},{label:'20–50名',min:20,max:50}]
export const amountShortcuts = [
  {label:'5000以上',min:5000,max:null}, {label:'10000–5000',min:5000,max:10000},
  {label:'5000–10000',min:5000,max:10000}, {label:'1000–5000',min:1000,max:5000},
  {label:'500–1000',min:500,max:1000}, {label:'100–500',min:100,max:500},
  {label:'1–100',min:1,max:100},
]
export function revenueChange(change) {
  if (!change || change.state === 'unavailable') return '无可比周期'
  if (change.state === 'new') return '基期为0'
  if (change.state === 'zero') return '无变化'
  const value=Number(change.rate)
  return `${value>0?'+':''}${value.toFixed(2)}%`
}
export function revenueAmount(value) {
  return value == null ? '—' : Number(value).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
}
export function normalizedRange(min,max) {
  const lower=min==null||min===''?undefined:Number(min)
  const upper=max==null||max===''?undefined:Number(max)
  return lower!==undefined&&upper!==undefined&&lower>upper?[upper,lower]:[lower,upper]
}
