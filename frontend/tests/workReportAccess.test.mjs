import test from 'node:test'
import assert from 'node:assert/strict'
import {reportScopePeople,reportViewingPrincipal} from '../src/utils/workReportAccess.js'

test('Lulu 和 Ethan 的范围预览与赵震锋使用同一规则',()=>{
 const catalog={configurator_id:'zhao',inherited_viewer_ids:['lulu','ethan']}
 assert.equal(reportViewingPrincipal(catalog,'lulu'),'zhao')
 assert.equal(reportViewingPrincipal(catalog,'ethan'),'zhao')
 assert.equal(reportViewingPrincipal(catalog,'other'),'other')
 assert.equal(reportViewingPrincipal({},'other'),'other')
})

test('发送范围合并去重，全部部门与全体成员区分，排除停用人员',()=>{
 const people=[{id:'a',active:true,departments:[]},{id:'b',active:true,departments:[{id:'it'},{id:'hr'}]},{id:'c',active:false,departments:[{id:'it'}]}]
 const ids=scope=>reportScopePeople(scope,people).map(person=>person.id)
 assert.deepEqual(ids({senders_all:true}),['a','b'])
 assert.deepEqual(ids({all_departments:true}),['b'])
 assert.deepEqual(ids({department_ids:['it'],sender_ids:['a','b']}),['a','b'])
 assert.deepEqual(ids({department_ids:['missing']}),[])
})
