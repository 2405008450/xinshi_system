export function departmentNameFor(row,names={}){
  const uid=row.user_id||row.person_id||row.userId||row.id
  return names[uid]||row.department_name||row.primaryDepartment||names[`name:${row.name}`]||row.department||'未分配部门'
}

export function departmentPagedLists(items,{names={},grouped=false,page=1,pageSize=20,server=false}={}){
  const rows=[...(items||[])]
  if(!server)rows.sort((a,b)=>{
    const department=grouped?departmentNameFor(a,names).localeCompare(departmentNameFor(b,names),'zh-CN'):0
    const person=String(a.name||'').localeCompare(String(b.name||''),'zh-CN')||String(a.user_id||a.person_id||'').localeCompare(String(b.user_id||b.person_id||''))
    const date=row=>String(row.day||row.month||row.start_at||row.start_date||row.created_at||'')
    return department||(grouped?person:0)||date(b).localeCompare(date(a))
  })
  const current=server?rows:rows.slice((page-1)*pageSize,page*pageSize),groups=new Map()
  for(const row of current){
    const name=grouped?departmentNameFor(row,names):''
    if(!groups.has(name))groups.set(name,{name,rows:[]})
    groups.get(name).rows.push(row)
  }
  return {total:rows.length,groups:[...groups.values()]}
}
