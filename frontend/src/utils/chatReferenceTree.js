// 先按父子关系排列，再按时间编号保持同一分支内的顺序；不修改接口对象。
export function referenceTreeRows(items) {
  const nodes=new Map(items.map(row=>[String(row.id),{...row,children:[]}]))
  const roots=[]
  for(const row of nodes.values()){
    const candidates=[...(row.ancestorIds || [])].reverse()
    const parent=candidates.map(id=>nodes.get(String(id))).find(node=>node && node.id!==row.id)
    if(parent)parent.children.push(row);else roots.push(row)
  }
  const result=[],seen=new Set()
  function visit(rows){
    for(const row of rows.sort((a,b)=>a.referenceNumber-b.referenceNumber)){
      if(seen.has(String(row.id)))continue
      seen.add(String(row.id));result.push(row);visit(row.children)
    }
  }
  visit(roots)
  return result
}

export function referenceGraphRoot(original,items){
  if(!original)return null
  const rows=referenceTreeRows(items)
  const nested=new Set(rows.flatMap(row=>row.children.map(child=>String(child.id))))
  return {...original,isOriginal:true,children:rows.filter(row=>!nested.has(String(row.id)))}
}
