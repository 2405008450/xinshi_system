import assert from 'node:assert/strict'
import test from 'node:test'
import { arrangementCellChanged, arrangementCellPayload, arrangementProjectRoute, arrangementTargetKey } from '../src/utils/resourceArrangements.js'

test('同语种不同需求和自选方向互不混淆', () => {
  const values = [{kind:'request',request_id:'one',language_id:'dialect'}, {kind:'request',request_id:'two',language_id:'dialect'}, {kind:'manual',language_id:'dialect'}, {kind:'internal'}]
  assert.equal(new Set(values.map(arrangementTargetKey)).size,4)
})
test('保存载荷不提交名称快照、完成信息或其他账号', () => {
  const cell={platform_id:'p',owner_id:'u',owner_name:'负责人',targets:[{kind:'request',request_id:'r',language_id:'l',label:'旧快照',active:false}],manual_projects:[{source_type:'annotation',project_id:'child',project_name:'子订单'}],remarks:'备注',completed:true,completed_by:'actor'}
  assert.deepEqual(arrangementCellPayload(cell),{platform_id:'p',owner_id:'u',targets:[{kind:'request',request_id:'r',language_id:'l'}],projects:[{source_type:'annotation',project_id:'child'}],remarks:'备注'})
  assert.equal(arrangementCellChanged({...cell,completed:false},cell),false)
  assert.equal(arrangementCellChanged({...cell,owner_id:'other'},cell),true)
})
test('子订单链接精确定位子订单及母项目', () => {
  assert.deepEqual(arrangementProjectRoute({source_type:'annotation',project_id:'child',parent_project_id:'parent'}),{name:'AnnotationChildOrders',query:{projectId:'child',parentProjectId:'parent'}})
  assert.deepEqual(arrangementProjectRoute({source_type:'translation',project_id:'translation'}),{name:'TranslationProjectDetails',query:{projectId:'translation'}})
})
