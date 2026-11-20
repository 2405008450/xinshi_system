import test from 'node:test'
import assert from 'node:assert/strict'
import {groupStatementClientsByMonth} from '../src/utils/statementClientMonths.js'

test('按客户合并月份，保留月份版本、进度和子客户范围',()=>{
  const october={id:'a',shortName:'客户甲',projectCount:2,version:'oct',progress:'partial',clientManagers:['甲'],subClients:[{id:'child-a'}]}
  const november={id:'a',shortName:'客户甲',projectCount:3,version:'nov',progress:'completed',clientManagers:['乙'],subClients:[{id:'child-b'}]}
  const result=groupStatementClientsByMonth([{month:'2026-11',items:[november]},{month:'2026-10',items:[october]}])
  assert.equal(result.length,1)
  assert.equal(result[0].projectCount,5)
  assert.deepEqual(result[0].clientManagers,['甲','乙'])
  assert.deepEqual(result[0].months.map(entry=>entry.month),['2026-10','2026-11'])
  assert.strictEqual(result[0].months[0].client,october)
  assert.strictEqual(result[0].months[1].client,november)
})

test('同名不同编号客户不合并，重复月份不重复计数，原输入不改变',()=>{
  const source=[{month:'2026-10',items:[{id:'b',name:'同名',projectCount:2},{id:'a',name:'同名',projectCount:3}]},
    {month:'2026-10',items:[{id:'a',name:'同名',projectCount:3}]}]
  const before=JSON.stringify(source)
  const result=groupStatementClientsByMonth(source)
  assert.deepEqual(result.map(client=>[client.id,client.projectCount]),[['a',3],['b',2]])
  assert.equal(JSON.stringify(source),before)
  assert.deepEqual(groupStatementClientsByMonth([]),[])
})
