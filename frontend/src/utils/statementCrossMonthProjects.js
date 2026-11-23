export function orderNumberMonth(number) {
  const match=String(number||'').match(/^[a-z]+-(\d{2})(0[1-9]|1[0-2])\d{2}-/i)
  return match?`20${match[1]}-${match[2]}`:null
}

export function crossMonthStatementProjects(tasks, boardId) {
  const projects=new Map()
  for(const task of Object.values(tasks||{})) {
    if(task.pending||task.board_id!==boardId)continue
    for(const line of task.rows||[]) {
      const sourceMonth=orderNumberMonth(line.order_no)
      if(!sourceMonth||sourceMonth===task.month)continue
      const orderNo=String(line.order_no).split('.')[0]
      const key=`${line.root_id||orderNo}:${task.month}`
      if(!projects.has(key))projects.set(key,{orderNo,projectName:line.project_name,sourceMonth,billingMonth:task.month,rootId:line.root_id})
    }
  }
  return [...projects.values()].sort((a,b)=>a.billingMonth.localeCompare(b.billingMonth)||a.orderNo.localeCompare(b.orderNo))
}
