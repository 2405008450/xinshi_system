// 单价仅在对外展示时四舍五入，不改变原始单价和金额计算。
export function statementTaxLabel(statement){const labels=new Set((statement.rows||[]).map(row=>row.unit_label).filter(label=>['含税','不含税'].includes(label)));return labels.size>1?'含税／不含税（按项目）':statement.tax_included?'含税':'不含税'}
export function statementUnitPrice(value){
  if(value==null||value==='')return '-'
  const match=String(value).trim().match(/^([+-]?)(\d+)(?:\.(\d*))?$/)
  if(!match)return Number.isFinite(Number(value))?Number(value).toFixed(3):'-'
  const decimals=(match[3]||'').padEnd(4,'0')
  let scaled=BigInt(match[2])*1000n+BigInt(decimals.slice(0,3))
  if(Number(decimals[3])>=5)scaled++
  return `${match[1]==='-'&&scaled?'-':''}${scaled/1000n}.${String(scaled%1000n).padStart(3,'0')}`
}

export const statementColumnWeights={received_date:24,project_name:35.7,language_pair:17.6,workload:29.7,unit_price:30,subtotal:22,remarks:34}
export const statementBasis=value=>String(value||'').replace(/[（(]每1(?:\.0+)?计价[）)]/g,'')
export const isFixedStatementRow=row=>row?.pricing_mode==='fixed'||(!row?.pricing_mode&&String(row?.basis||'').split('\n')[0]==='固定收费')

export const statementTitle=statement=>{const title=statement.title||'对账单',prefix=statement.month?`${statement.month} `:'';return prefix&&title.startsWith(prefix)?title.slice(prefix.length):title}

export const statementFileStem=name=>String(name||'客户对账单').replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').replace(/[. ]+$/,'').slice(0,120).replace(/(?:\.(?:xlsx|pdf))+$/i,'')||'客户对账单'
export const statementFileName=(name,format='excel')=>statementFileStem(name)+(format==='pdf'?'.pdf':'.xlsx')
