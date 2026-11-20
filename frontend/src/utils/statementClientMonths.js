// 同一客户按稳定编号合并，保留各月份独立的版本、进度、子客户及操作范围。
export function groupStatementClientsByMonth(sources){
  const clients=new Map()
  for(const {month,items} of [...sources].sort((a,b)=>a.month.localeCompare(b.month))){
    for(const item of items){
      let client=clients.get(item.id)
      if(!client){
        client={id:item.id,name:item.name,shortName:item.shortName,code:item.code,projectCount:0,clientManagers:[],months:[]}
        clients.set(item.id,client)
      }
      if(client.months.some(entry=>entry.month===month))continue
      client.months.push({month,client:item})
      client.projectCount+=item.projectCount||0
      client.clientManagers=[...new Set([...client.clientManagers,...(item.clientManagers||[])])]
    }
  }
  return [...clients.values()].sort((a,b)=>(a.shortName||a.name||'').localeCompare(b.shortName||b.name||'','zh-CN')||a.id.localeCompare(b.id))
}
