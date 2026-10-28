export function dutyCounts(assignments){const result={};for(const row of assignments)result[row.user_id]=(result[row.user_id]||0)+1;return result}
export function dutyCountDistribution(people,counts){const result={};for(const id of new Set(people.map(person=>person.id))){const count=counts[id]||0;result[count]=(result[count]||0)+1}return Object.entries(result).map(([count,people])=>({count:Number(count),people})).sort((a,b)=>a.count-b.count)}
export function dutyDateLabel(date){const day=new Date(`${date}T12:00:00Z`).getUTCDay();return `${Number(date.slice(5,7))}月${Number(date.slice(8))}日 ${day===6?'周六':'周日'}`}
export function applyDutyDrop(assignments,ids,date,department,sourceDate=null){
 const selected=new Set(ids)
 return [...assignments.filter(row=>!selected.has(row.user_id)||(row.date!==date&&row.date!==sourceDate)),...[...selected].map(user_id=>({user_id,date,department}))]
}
