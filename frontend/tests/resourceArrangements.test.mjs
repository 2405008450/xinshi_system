import assert from 'node:assert/strict'
import test from 'node:test'
import { arrangementCellChanged, arrangementCellPayload, arrangementProjectRoute, arrangementTargetKey, normalizeArrangementRoles, arrangementChineseTime } from '../src/utils/resourceArrangements.js'

test('同语种不同需求和自选方向互不混淆', () => {
  const values = [{kind:'request',request_id:'one',language_id:'dialect'}, {kind:'request',request_id:'two',language_id:'dialect'}, {kind:'manual',language_id:'dialect'}, {kind:'internal'}]
  assert.equal(new Set(values.map(arrangementTargetKey)).size,4)
})
test('保存载荷不提交名称快照、完成信息或其他账号', () => {
  const cell={platform_id:'p',owner_id:'u',owner_name:'负责人',targets:[{kind:'request',request_id:'r',language_id:'l',label:'旧快照',active:false}],manual_projects:[{source_type:'annotation',project_id:'child',project_name:'子订单'}],remarks:'备注',completed:true,completed_by:'actor'}
  assert.deepEqual(arrangementCellPayload(cell),{platform_id:'p',owner_id:'u',targets:[{kind:'request',request_id:'r',language_id:'l'}],role_tags:[],projects:[{source_type:'annotation',project_id:'child'}],remarks:'备注'})
  assert.equal(arrangementCellChanged({...cell,completed:false},cell),false)
  assert.equal(arrangementCellChanged({...cell,owner_id:'other'},cell),true)
})
test('岗位标签独立于语种，兼容旧数据并规范空白与重复项', () => {
  assert.deepEqual(normalizeArrangementRoles([' HR ', '', '客服', 'HR', '  ']), ['HR','客服'])
  const cell = { platform_id:'boss1', role_tags:[' HR ', '客服', 'HR'] }
  assert.deepEqual(arrangementCellPayload(cell).role_tags, ['HR','客服'])
  assert.deepEqual(arrangementCellPayload(cell).targets, [])
  assert.deepEqual(arrangementCellPayload({platform_id:'boss2'}).role_tags, [])
  assert.equal(arrangementCellChanged({...cell,role_tags:[]},cell),true)
})
test('完成时间统一显示 UTC+8，兼容已确认的本地历史值', () => {
  assert.equal(arrangementChineseTime('2026-10-09T09:18:43Z'), arrangementChineseTime('2026-10-09T17:18:43+08:00'))
  assert.equal(arrangementChineseTime('2026-10-09T17:18:43'), arrangementChineseTime('2026-10-09T17:18:43+08:00'))
  assert.equal(arrangementChineseTime(null), '-')
  assert.equal(arrangementChineseTime('invalid'), '-')
})
test('子订单链接精确定位子订单及母项目', () => {
  assert.deepEqual(arrangementProjectRoute({source_type:'annotation',project_id:'child',parent_project_id:'parent'}),{name:'AnnotationChildOrders',query:{projectId:'child',parentProjectId:'parent'}})
  assert.deepEqual(arrangementProjectRoute({source_type:'translation',project_id:'translation'}),{name:'TranslationProjectDetails',query:{projectId:'translation'}})
})
