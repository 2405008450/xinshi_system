import test from 'node:test'
import assert from 'node:assert/strict'
import {mergeSavedRecord,sameSavedValue} from '../src/utils/savedDataMerge.js'
test('未修改字段自动接收最新保存值，snake与camel字段共用规则',()=>{
 const target={id:'one',projectName:'旧名称',projectStatus:'confirmed',remark:'我的草稿'},changes=[]
 mergeSavedRecord(target,{id:'one',project_name:'旧名称',project_status:'confirmed',remark:'旧备注'},{id:'one',project_name:'新名称',project_status:'sent_to_client',remark:'他人保存的备注'},(...args)=>changes.push(args))
 assert.equal(target.projectName,'新名称');assert.equal(target.projectStatus,'sent_to_client');assert.equal(target.remark,'我的草稿');assert.equal(changes.length,1);assert.equal(changes[0][0],'remark')
})
test('没有服务端变化时不动本地输入，未知字段不塞入编辑表单',()=>{
 const target={name:'未保存输入',localOnly:true};mergeSavedRecord(target,{name:'旧值'},{name:'旧值',created_at:'2026-11-05T00:00:00+08:00'})
 assert.deepEqual(target,{name:'未保存输入',localOnly:true})
})
test('列表更新保留现有行引用和草稿，新增删除使用服务端结果',()=>{
 const row={id:'one',projectName:'本地草稿'},target={items:[row,{id:'removed',projectName:'旧',derivedLabel:'显示用字段'}]}
 mergeSavedRecord(target,{items:[{id:'one',project_name:'原值'},{id:'removed',project_name:'旧'}]},{items:[{id:'one',project_name:'服务端'},{id:'new',project_name:'新项目'}]})
 assert.equal(target.items[0],row);assert.equal(row.projectName,'本地草稿');assert.deepEqual(target.items.map(row=>row.id),['one','new']);assert.equal(target.items[1].projectName,'新项目')
})
test('删除存在未保存修改的行时保留输入并提示',()=>{
 const target={items:[{id:'one',name:'未保存'}]},conflicts=[]
 mergeSavedRecord(target,{items:[{id:'one',name:'旧值'}]},{items:[]},(...args)=>conflicts.push(args))
 assert.equal(target.items.length,1);assert.equal(conflicts.length,1)
})
test('嵌套字段独立合并，零金额和空值不混淆',()=>{
 const target={taxPrices:{unitPriceExclTax:0,unitPriceInclTax:20}},conflicts=[]
 mergeSavedRecord(target,{tax_prices:{unit_price_excl_tax:null,unit_price_incl_tax:20}},{tax_prices:{unit_price_excl_tax:12,unit_price_incl_tax:30}},(...args)=>conflicts.push(args))
 assert.equal(target.taxPrices.unitPriceExclTax,0);assert.equal(target.taxPrices.unitPriceInclTax,30);assert.equal(conflicts[0][0],'taxPrices.unitPriceExclTax')
 assert.equal(sameSavedValue(0,null),false);assert.equal(sameSavedValue(0.12,'0.1200'),true)
})
