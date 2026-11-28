// 同一账号的未保存内容继续恢复；已保存人选的姓名与勾选由新详情补齐。
const id=row=>String(row?.translatorId||'')
const ids=rows=>(rows||[]).map(id).filter(Boolean)
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b)
export function restoreInterpreterAssignments(draftRows,savedRows,baselineRows,stale=false){
 const local=Array.isArray(draftRows)?draftRows:[],saved=Array.isArray(savedRows)?savedRows:[]
 const bySaved=new Map(saved.filter(id).map(row=>[id(row),row]))
 let rows=local
 if(Array.isArray(baselineRows)){
  const baseline=new Map(baselineRows.filter(id).map(row=>[id(row),row]))
  if(same(ids(local),ids(baselineRows))){
   const byLocal=new Map(local.filter(id).map(row=>[id(row),row]))
   rows=saved.map(row=>{
    const before=baseline.get(id(row)),pending=byLocal.get(id(row))
    if(!before||!pending)return {...row}
    const result={...row,...pending}
    for(const key of ['clientSelected','customerRating','evaluationNote','contractPath','languageIds','rates'])if(same(pending[key],before[key]))result[key]=row[key]
    return result
   })
  }
 }else if(local.length&&!ids(local).length&&saved.length){
  // 旧版自动暂存的空白占位行不表示用户删除了已有译员。
  rows=saved
 }else if(stale&&same(ids(local),ids(saved))){
  rows=local.map(row=>({...row,clientSelected:bySaved.get(id(row))?.clientSelected??row.clientSelected}))
 }
 return rows.map(row=>{const saved=bySaved.get(id(row)),result={...row,translatorLabel:row.translatorLabel||saved?.translatorLabel||''};for(const key of ['contractPath','languageIds','rates'])if(result[key]===undefined&&saved?.[key]!==undefined)result[key]=saved[key];return result})
}
