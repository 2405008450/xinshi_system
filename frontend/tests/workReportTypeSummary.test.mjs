import test from 'node:test'
import assert from 'node:assert/strict'
import {summarizeReportTypes,reportItemsSortedByType} from '../src/utils/workReportTypeSummary.js'

test('同一类型内相同项目和具体任务累计，不同项目分开，多选类型分别计入',()=>{
 const row=(name,minutes,types,project='p')=>({task_name:name,progress_content:'处理文档',duration_minutes:minutes,display_metadata:{project_id:project,report_types:types}})
 const items=[row('项目甲',10,['笔译项目']),row('项目甲',15,['笔译项目']),row('项目乙',20,['笔译项目'],'q'),row('项目甲',30,['笔译项目','管理工作','管理工作'])]
 const before=JSON.stringify(items),groups=summarizeReportTypes(items)
 const translation=groups.find(group=>group.type==='项目工作'),management=groups.find(group=>group.type==='管理工作')
 assert.equal(translation.minutes,75);assert.equal(translation.tasks.length,2)
 assert.equal(translation.tasks[0].minutes,55);assert.equal(translation.tasks[0].count,3)
 assert.equal(translation.children[0].type,'笔译项目');assert.equal(translation.children[0].minutes,75)
 assert.equal(management.minutes,30);assert.equal(management.tasks[0].count,1)
 assert.equal(JSON.stringify(items),before)
})

test('先汇总斜杠前的大类，再统计同名子类；同一任务多选同一大类的子类不重复计大类时间',()=>{
 const email='邮件+微信+系统沟通等',admin='行政工作'
 const row=(minutes,types)=>({duration_minutes:minutes,display_metadata:{report_types:types}})
 const items=[row(30,[`非项目工作::${email}`]),row(15,[`非项目工作::${admin}`]),row(20,[`非项目工作::${email}`]),row(10,[`非项目工作::${email}`,`非项目工作::${admin}`,`非项目工作::${email}`])]
 const groups=summarizeReportTypes(items)
 assert.equal(groups.length,1);assert.equal(groups[0].label,'非项目工作');assert.equal(groups[0].minutes,75)
 assert.equal(groups[0].children.length,2)
 assert.equal(groups[0].children.find(child=>child.type===email).minutes,60)
 assert.equal(groups[0].children.find(child=>child.type===admin).minutes,25)
 const legacy=summarizeReportTypes([{task_type:`非项目工作 / ${email}`,duration_minutes:5}])
 assert.equal(legacy[0].type,'非项目工作');assert.equal(legacy[0].children[0].label,email)
})

test('排序依次按大类、子类聚拢；同一子类保持原明细顺序',()=>{
 const row=type=>({display_metadata:{report_types:[type]}})
 const sorted=reportItemsSortedByType([row('非项目工作::邮件'),row('财务工作::客户对账'),row('非项目工作::行政'),row('非项目工作::邮件')])
 const email=sorted.filter(row=>[0,3].includes(row.index))
 assert.deepEqual(email.map(row=>row.index),[0,3])
 assert.equal(sorted.indexOf(email[1])-sorted.indexOf(email[0]),1)
 const positions=sorted.map((row,index)=>row.index===1?null:index).filter(index=>index!==null)
 assert.equal(positions.at(-1)-positions[0],2)
})

test('按第一任务类型稳定排序，每个原始明细只出现一次并保留原索引',()=>{
 const items=[{task_type:'管理工作',duration_minutes:30},{task_type:'笔译项目',duration_minutes:15},{task_type:'管理工作',duration_minutes:10}]
 const sorted=reportItemsSortedByType(items)
 assert.equal(sorted.length,3);assert.equal(new Set(sorted.map(row=>row.index)).size,3)
 const management=sorted.filter(row=>row.item.task_type==='管理工作')
 assert.deepEqual(management.map(row=>row.index),[0,2])
 assert.equal(Math.abs(sorted.indexOf(management[0])-sorted.indexOf(management[1])),1)
 assert.deepEqual(summarizeReportTypes([]),[])
})
