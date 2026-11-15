export function indexFinanceClientOrders(roots,isExpanded=()=>true){
  let total=0
  function index(node){
    const start=total+1
    const orderIndex=++total
    const children=isExpanded(node.id)?(node.children||[]).map(index):[]
    return {node,start,end:total,orderIndex,children}
  }
  const orders=roots.map(index)
  return {orders,total}
}

export function sliceFinanceClientOrders(orders,page,pageSize){
  const first=(page-1)*pageSize+1,last=first+pageSize-1
  function slice(entry){
    if(entry.end<first||entry.start>last)return []
    return [{...entry.node,hasChildren:!!entry.node.children?.length,
      pageIndex:entry.orderIndex>=first&&entry.orderIndex<=last?entry.orderIndex:null,
      children:entry.children.flatMap(slice)}]
  }
  return orders.flatMap(slice)
}

// Ancestors outside the page keep the response tree intact but do not take up a table row.
export function financeOrderPageRows(rows){
  return rows.flatMap(row=>{
    const children=financeOrderPageRows(row.children||[])
    return row.pageIndex==null?children:[{...row,children}]
  })
}

export function financeParentOrderRows(rows){
  return rows.map(row=>({...row,hasChildren:row.hasChildren??!!row.children?.length,children:[]}))
}

export function financeDisplayIndexes(rows, offset = 0, indexes = new Map()){
  let index = offset
  function number(row){
    indexes.set(row.id, ++index)
    row.children?.forEach(number)
  }
  rows.forEach(number)
  return indexes
}
