import test from 'node:test'
import assert from 'node:assert/strict'
import {dutyCounts,dutyCountDistribution,applyDutyDrop,dutyDateLabel} from '../src/utils/weekendDuty.js'
test('同一人员不同周末重复安排，次数按右侧出现次数计，重复放同一天不翻倍',()=>{
 let rows=applyDutyDrop([],['a'],'2026-11-01','customer')
 rows=applyDutyDrop(rows,['a'],'2026-11-07','customer');assert.deepEqual(dutyCounts(rows),{a:2})
 rows=applyDutyDrop(rows,['a'],'2026-11-07','project');assert.equal(rows.length,2);assert.equal(rows[1].department,'project')
 const moved=applyDutyDrop(rows,['a'],'2026-11-08','project','2026-11-07');assert.deepEqual(dutyCounts(moved),{a:2});assert.equal(moved[1].date,'2026-11-08')
 assert.deepEqual(dutyCounts(moved.filter(row=>row.date!=='2026-11-08')),{a:1})
})
test('次数分布含0次并按唯一人员去重，支持多次筛选所需统计',()=>{
 assert.deepEqual(dutyCountDistribution([{id:'a'},{id:'b'},{id:'c'},{id:'a'}],{a:2,b:1}),[{count:0,people:1},{count:1,people:1},{count:2,people:1}])
})
test('多人一次拖入去重，并保留其他人员原安排',()=>{
 const rows=applyDutyDrop([{user_id:'a',date:'2026-11-01',department:'it'}],['b','c','b'],'2026-11-07','project')
 assert.equal(rows.length,3);assert.deepEqual(dutyCounts(rows),{a:1,b:1,c:1})
})
test('日期标签不依赖浏览器默认时区',()=>{assert.equal(dutyDateLabel('2026-11-07'),'11月7日 周六');assert.equal(dutyDateLabel('2026-11-01'),'11月1日 周日')})
