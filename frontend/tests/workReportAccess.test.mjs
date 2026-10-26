import test from 'node:test'
import assert from 'node:assert/strict'
import {reportScopePeople} from '../src/utils/workReportAccess.js'

test('发送范围合并去重，全部部门与全体成员区分，排除停用人员',()=>{
 const people=[{id:'a',active:true,departments:[]},{id:'b',active:true,departments:[{id:'it'},{id:'hr'}]},{id:'c',active:false,departments:[{id:'it'}]}]
 const ids=scope=>reportScopePeople(scope,people).map(person=>person.id)
 assert.deepEqual(ids({senders_all:true}),['a','b'])
 assert.deepEqual(ids({all_departments:true}),['b'])
 assert.deepEqual(ids({department_ids:['it'],sender_ids:['a','b']}),['a','b'])
 assert.deepEqual(ids({department_ids:['missing']}),[])
})
