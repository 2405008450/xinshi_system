import test from 'node:test'
import assert from 'node:assert/strict'
import {durationOptions,durationLabel,normalizeReportRow,rowTypes,updateRowTypes,shiftReportDate,reportWeekday,validQuantity,buildWorkTypeOptions,appendReportRows,requiresProjectIdentity,blockReportImages} from '../src/utils/workReportForm.js'
test('耗时按10分钟和0.1小时生成，存储仍为整数分钟',()=>{
 assert.deepEqual(durationOptions.slice(0,8),[10,20,30,40,50,60,66,72]);assert.equal(durationOptions.at(-1),1440)
 assert.equal(durationLabel(60),'60分钟');assert.equal(durationLabel(66),'1.1小时');assert.equal(durationLabel(72),'1.2小时')
})
test('多种项目类型、工作量和旧来源信息可同时保留',()=>{
 const row=normalizeReportRow({source_type:'manual',task_type:'旧类型',duration_minutes:20,display_metadata:{order_no:'AP-001',quantity:1.5,quantity_unit:'页'}})
 assert.deepEqual(rowTypes(row),['标注项目']);updateRowTypes(row,['标注项目','笔译项目','非项目工作'])
 assert.equal(row.task_type,'项目工作、非项目工作');assert.equal(row.display_metadata.quantity,1.5);assert.equal(row.display_metadata.order_no,'AP-001')
})
test('日期和星期固定UTC+8，跨月跨年正确',()=>{
 assert.equal(shiftReportDate('2026-12-31',1),'2027-01-01');assert.equal(shiftReportDate('2026-03-01',-1),'2026-02-28');assert.equal(reportWeekday('2026-10-24'),'星期六')
})
test('工作量支持小数和空值，拒绝负数非数字',()=>{for(const n of ['',null,0,'1.25'])assert.equal(validQuantity(n),true);for(const n of ['x',-1,Infinity])assert.equal(validQuantity(n),false)})

test('四类工作保留层级，只有纯非项目工作免填订单和项目名称',()=>{
 const options=buildWorkTypeOptions();assert.deepEqual(options.map(option=>option.label),['项目工作','非项目工作','外勤工作','管理工作'])
 for(const types of [['非项目工作'],['非项目工作::接待客户']])assert.equal(requiresProjectIdentity({display_metadata:{report_types:types}}),false)
 for(const types of [['笔译项目'],['外勤工作::拜访客户'],['管理工作::分析数据'],['非项目工作::接待客户','管理工作::分析数据']])assert.equal(requiresProjectIdentity({display_metadata:{report_types:types}}),true)
 const row={display_metadata:{}};updateRowTypes(row,['外勤工作::拜访客户','管理工作::分析数据']);assert.equal(row.task_type,'外勤工作、管理工作')
})

test('批量加行校验数量且各行独立',()=>{
 const rows=[];appendReportRows(rows,3);assert.equal(rows.length,3);rows[0].display_metadata.quantity=1;assert.equal(rows[1].display_metadata.quantity,undefined)
 for(const count of [0,-1,1.5,101,null])assert.throws(()=>appendReportRows(rows,count));assert.equal(rows.length,3)
})

test('非项目等分类的其他选项不会与自定义占位重复',()=>{
 const options=buildWorkTypeOptions(undefined,[{display_metadata:{report_types:['非项目工作::__custom__']}}])
 for(const parent of ['非项目工作','外勤工作','管理工作']){
  const children=options.find(option=>option.value===parent).children
  assert.equal(children.filter(option=>option.value===`${parent}::__custom__`).length,1)
  assert.equal(children.find(option=>option.value===`${parent}::__custom__`).label,'其他（自定义）')
 }
})

test('阻止图片与截图引用，保留Excel文字粘贴',()=>{
 for(const [files,text,html,blocked] of [[[{type:'image/png'}],'','',true],[[],'screenshot://abc','',true],[[],'','<img src="x">',true],[[],'A\tB\nC\tD','<table></table>',false]]){
  let prevented=false;const event={clipboardData:{files,getData:type=>type==='text/plain'?text:html},preventDefault(){prevented=true},stopPropagation(){}}
  assert.equal(blockReportImages(event),blocked);assert.equal(prevented,blocked)
 }
})
