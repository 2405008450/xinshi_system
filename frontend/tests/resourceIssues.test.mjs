import assert from 'node:assert/strict'
import test from 'node:test'
import { cleanIssueColumns, defaultIssueColumns, issueParams, hongKongToday, issueDateLabel, issueStatusSummary } from '../src/utils/resourceIssues.js'

test('字段配置保留全部取消，清理历史键及重复键',()=>{
  assert.deepEqual(cleanIssueColumns([]),[])
  assert.deepEqual(cleanIssueColumns(['content','deleted','content','remarks']),['content','remarks'])
  assert.throws(()=>cleanIssueColumns({}))
  assert.ok(defaultIssueColumns.includes('planned_completion_at'))
  assert.ok(defaultIssueColumns.includes('actual_progress'))
  assert.ok(defaultIssueColumns.includes('proposer_name'))
})
test('分页与所有高级条件使用同一份参数',()=>{
  const filters={keyword:' 资源 ',category:'problem',proposer_id:'a',executor_id:'b',status:'completed',range:['2026-10-01','2026-10-12']}
  assert.deepEqual(issueParams(filters,{page:3,limit:20}),{keyword:'资源',category:'problem',proposer_id:'a',executor_id:'b',status:'completed',planned_start:'2026-10-01',planned_end:'2026-10-12',skip:40,limit:20})
  assert.equal(issueParams({...filters,keyword:' ',range:null},{page:1,limit:10}).keyword,undefined)
})
test('香港当天跨日及纯日期展示不依赖浏览器时区',()=>{
  assert.equal(hongKongToday(new Date('2026-10-11T16:00:00Z')),'2026-10-12')
  assert.equal(hongKongToday(new Date('2026-10-11T15:59:59Z')),'2026-10-11')
  assert.equal(issueDateLabel('2026-10-12'),'2026年10月12日')
  assert.equal(issueDateLabel(null),'-')
})
test('状态汇总保留取消任务并忽略空状态',()=>{
  assert.equal(issueStatusSummary({pending:1,completed:2,cancelled:1}),'未开始 1 · 已完成 2 · 已取消 1')
  assert.equal(issueStatusSummary({}),'-')
})
