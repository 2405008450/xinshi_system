export function indexFinanceClientOrders(roots){
  let total=0
  function index(node,counted){
    const start=total+1
    const orderIndex=counted?++total:null
    const children=(node.children||[]).map(child=>index(child,true))
    return {node,start,end:total,orderIndex,children}
  }
  const orders=roots.map(root=>index(root,!root.children?.length))
  return {orders,total}
}

export function sliceFinanceClientOrders(orders,page,pageSize){
  const first=(page-1)*pageSize+1,last=first+pageSize-1
  function slice(entry){
    if(entry.end<first||entry.start>last)return []
    return [{...entry.node,hasChildren:entry.children.length>0,
      pageIndex:entry.orderIndex>=first&&entry.orderIndex<=last?entry.orderIndex:null,
      children:entry.children.flatMap(slice)}]
  }
  return orders.flatMap(slice)
}

export function financeClientDisplayOffset(orders, page, pageSize){
  const previousEnd = (page - 1) * pageSize
  let offset = 0
  function count(entry){
    const last = Math.min(entry.end, previousEnd)
    if(entry.start > last) return
    offset += Math.floor((last - 1) / pageSize) - Math.floor((entry.start - 1) / pageSize) + 1
    entry.children.forEach(count)
  }
  orders.forEach(count)
  return offset
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
