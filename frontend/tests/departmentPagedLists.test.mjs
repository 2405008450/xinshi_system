import test from 'node:test'
import assert from 'node:assert/strict'
import {departmentNameFor,departmentPagedLists} from '../src/utils/departmentPagedLists.js'

test('先按主部门和人员排序，再分页；数量不重复，源数据不改变',()=>{
 const items=Array.from({length:25},(_,index)=>({id:String(index),user_id:index%2?'alice':'bob',name:index%2?'甲':'乙',day:`2026-11-${String(index+1).padStart(2,'0')}`}))
 const names={alice:'HR部',bob:'IT部'},before=JSON.stringify(items)
 const pages=[1,2,3].map(page=>departmentPagedLists(items,{names,grouped:true,page,pageSize:10}))
 assert.ok(pages.every(page=>page.total===25))
 const groups=pages.flatMap(page=>page.groups),rows=groups.flatMap(group=>group.rows)
 assert.equal(rows.length,25);assert.equal(new Set(rows.map(row=>row.id)).size,25)
 assert.ok(rows.slice(0,12).every(row=>row.user_id==='alice'))
 assert.ok(rows.slice(12).every(row=>row.user_id==='bob'))
 assert.equal(JSON.stringify(items),before)
 assert.equal(departmentPagedLists(items,{names,grouped:true,pageSize:20}).groups.reduce((sum,g)=>sum+g.rows.length,0),20)
 assert.equal(departmentPagedLists(items,{names,grouped:true,pageSize:50}).groups.reduce((sum,g)=>sum+g.rows.length,0),25)
})

test('服务端已分页的明细不再截取或重排；空值和部门回退清晰',()=>{
 const result=departmentPagedLists([{user_id:'a',day:'2026-11-26'},{user_id:'b',department_name:'HR部'}],{names:{a:'IT部'},grouped:true,page:9,pageSize:10,server:true})
 assert.deepEqual(result.groups.map(group=>group.name),['IT部','HR部'])
 assert.equal(departmentNameFor({name:'未知人员'}),'未分配部门')
 assert.equal(departmentNameFor({name:'同事'},{'name:同事':'销售部'}),'销售部')
 assert.deepEqual(departmentPagedLists([]).groups,[])
})
