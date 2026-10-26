import test from 'node:test'
import assert from 'node:assert/strict'
import {newReportRow,reportBusinessDate} from '../src/utils/workReportForm.js'
import {appendChildRows,nestDuplicateOrder,reportOutline,syncReportChildren,parentRowKey,reportRowKey} from '../src/utils/workReportHierarchy.js'
const project=()=>({...newReportRow(),task_type:'项目工作',task_name:'测试项目',progress_content:'主任务',display_metadata:{report_types:['笔译项目'],order_no:'TP-001',quantity:20,quantity_unit:'字'}})
test('重复订单转二级且只复制项目身份，自己的任务内容保留',()=>{
 const first=project(),second={...project(),task_name:'覆盖名称',progress_content:'另一工作'};const rows=[first,second]
 assert.equal(nestDuplicateOrder(rows,second),true);assert.equal(parentRowKey(second),reportRowKey(first))
 assert.equal(second.task_name,'测试项目');assert.equal(second.progress_content,'另一工作');assert.deepEqual(reportOutline(rows),['1','1.1'])
 assert.equal(nestDuplicateOrder(rows,second),false)
})
test('一次新增多行，仅继承身份且保持两级结构',()=>{
 const rows=[project()];const children=appendChildRows(rows,rows[0],3)
 assert.deepEqual(reportOutline(rows),['1','1.1','1.2','1.3'])
 for(const child of children){assert.equal(child.progress_content,'');assert.equal(child.duration_minutes,0);assert.equal(child.display_metadata.quantity,undefined)}
 appendChildRows(rows,children[0],1);assert.deepEqual(reportOutline(rows),['1','1.1','1.2','1.3','1.4'])
 rows[0].task_name='新名称';rows[0].display_metadata.order_no='TP-002';syncReportChildren(rows)
 assert.equal(rows[4].task_name,'新名称');assert.equal(rows[4].display_metadata.order_no,'TP-002')
 assert.throws(()=>appendChildRows(rows,rows[0],0));assert.throws(()=>appendChildRows(rows,rows[0],101))
})
test('不同订单不归组，空编号不自动重复',()=>{
 const rows=[project(),project()];rows[1].display_metadata.order_no='TP-002';assert.equal(nestDuplicateOrder(rows,rows[1]),false)
 rows.forEach(row=>row.display_metadata.order_no='');assert.equal(nestDuplicateOrder(rows,rows[1]),false)
})
test('报告七点换日与浏览器时区无关',()=>{
 assert.equal(reportBusinessDate('2026-10-24T06:59:59+08:00'),'2026-10-23')
 assert.equal(reportBusinessDate('2026-10-24T07:00:00+08:00'),'2026-10-24')
 assert.equal(reportBusinessDate('2027-01-01T06:00:00+08:00'),'2026-12-31')
 assert.equal(reportBusinessDate('2026-10-23T23:00:00Z'),'2026-10-24')
})
