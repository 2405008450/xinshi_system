import test from 'node:test'
import assert from 'node:assert/strict'
import {statementBoardMonths,statementBoardMatchesMonths,pendingStatementTasksInScope} from '../src/utils/statementBoardMonths.js'

test('merged statements match any selected month and retain all month labels',()=>{
  const board={statement:{months:['2026-10','2026-11','2026-10']}}
  assert.deepEqual(statementBoardMonths(board),['2026-10','2026-11'])
  assert.equal(statementBoardMatchesMonths(board,['2026-11']),true)
  assert.equal(statementBoardMatchesMonths(board,['2026-09','2026-10']),true)
  assert.equal(statementBoardMatchesMonths(board,['2026-12']),false)
})
test('empty period boards match their declared months without needing rows',()=>{
  assert.equal(statementBoardMatchesMonths({period_month:'2026-11',statement:{months:[]}},['2026-11']),true)
  assert.equal(statementBoardMatchesMonths({billing_months:['2026-10'],statement:{months:[]}},['2026-11']),false)
})

test('pending rows match selected months and periods together',()=>{
  const tasks=[{id:'a',month:'2026-11',period_number:1},{id:'b',month:'2026-11',period_number:2},
    {id:'c',month:'2026-12',period_number:2},{id:'d',month:'2026-11',period_number:null}]
  const ids=scope=>pendingStatementTasksInScope(tasks,scope).map(row=>row.id)
  assert.deepEqual(ids({months:['2026-12']}),['c'])
  assert.deepEqual(ids({months:['2026-11'],periodNumber:2}),['b'])
  assert.deepEqual(ids({months:['2026-11','2026-12'],periodNumber:2}),['b','c'])
  assert.deepEqual(ids({months:['2026-11']}),['a','b','d'])
  assert.deepEqual(ids({months:[]}),[])
  assert.deepEqual(pendingStatementTasksInScope([{month:'2026-11',sub_client_id:'child'}],{months:['2026-11'],subClientId:'other'}),[])
})
