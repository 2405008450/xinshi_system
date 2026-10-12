import assert from 'node:assert/strict'
import test from 'node:test'
import { arrangementCellChanged, arrangementCellPayload, arrangementProjectRoute, arrangementTargetKey, normalizeArrangementRoles, arrangementChineseTime, groupArrangementAccounts, arrangementTableRows, arrangementTableSpan } from '../src/utils/resourceArrangements.js'

test('同语种不同需求和自选方向互不混淆', () => {
  const values = [{kind:'request',request_id:'one',language_id:'dialect'}, {kind:'request',request_id:'two',language_id:'dialect'}, {kind:'manual',language_id:'dialect'}, {kind:'internal'}, {kind:'request_project',request_id:'one'}]
  assert.equal(new Set(values.map(arrangementTargetKey)).size,5)
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

test('三大类按固定顺序分组，账号只按归属 ID 关联并保留表单索引', () => {
  const options = { arrangement_platforms: [
    { id:'boss', name:'BOSS', kind:'channel_group', category:'national', has_accounts:true },
    { id:'b2', name:'BOSS2', kind:'platform', parent_id:'boss', parent_name:'BOSS', category:'national' },
    { id:'b1', name:'BOSS1', kind:'platform', parent_id:'boss', parent_name:'BOSS', category:'national' },
    { id:'local', name:'泉州招聘网', kind:'platform', category:'local' },
    { id:'foreign', name:'Facebook', kind:'platform', category:'international' },
  ] }
  const cell = {platform_id:'b2',platform_name:'BOSS2历史名称',targets:[{kind:'manual',language_id:'l',label:'温州话'}]}
  const groups = groupArrangementAccounts(options, [cell])
  assert.deepEqual(groups.map(group => group.label), ['全国性平台','地方性平台','国外平台'])
  assert.deepEqual(groups[0].platforms[0].accounts.map(account => account.id), ['b1','b2'])
  const row = groups[0].platforms[0].accounts[1]
  assert.equal(row.cell, cell)
  assert.equal(row.index, 0)
  assert.equal(row.path, '全国性平台 / BOSS / BOSS2历史名称')
  assert.equal(groups[1].platforms[0].accounts[0].accountName, '单账号')
  assert.deepEqual(arrangementTableRows(groups).map(row => row.id), ['b1','b2','local','foreign'])
})

test('缺少关系信息时不从 BOSS 名称猜归属，同名独立平台按 ID 区分', () => {
  const rows = arrangementTableRows(groupArrangementAccounts({options:[
    {id:'a',kind:'platform',name:'BOSS1',category:'national'},
    {id:'b',kind:'platform',name:'BOSS1',category:'national'},
  ]}))
  assert.deepEqual(rows.slice(0,2).map(row => [row.platformId,row.platformSpan,row.accountName]), [['a',1,'单账号'],['b',1,'单账号']])
  assert.equal(rows[2].empty, true)
  assert.deepEqual(arrangementTableSpan({row:rows[2],columnIndex:1}), [1,7])
  assert.deepEqual(arrangementTableSpan({row:rows[2],columnIndex:7}), [0,0])
})

test('合并大类和平台单元格，未知分类及历史父平台安排均不丢失', () => {
  const options = {arrangement_platforms:[
    {id:'parent',kind:'platform',name:'旧主平台',category:'national',has_accounts:true},
    {id:'account',kind:'platform',name:'账号',parent_id:'parent',parent_name:'旧主平台',category:'national'},
    {id:'unknown',kind:'platform',name:'未知性质',category:''},
    {id:'empty-brand',kind:'channel_group',name:'空品牌',category:'local'},
  ]}
  const cells = [{platform_id:'gone',platform_name:'已移除的历史账号'}, {platform_id:'parent',platform_name:'父平台历史名称'}]
  const before = JSON.stringify(cells)
  const rows = arrangementTableRows(groupArrangementAccounts(options,cells,{includePlaceholders:true}))
  assert.deepEqual(rows.slice(0,2).map(row => [row.categorySpan,row.platformSpan]), [[2,2],[0,0]])
  assert.deepEqual(arrangementTableSpan({row:rows[1],columnIndex:0}), [0,0])
  assert.equal(rows.find(row => row.id === 'parent').cell, cells[1])
  assert.equal(rows.find(row => row.id === 'gone').categoryLabel, '待分类')
  assert.equal(rows.find(row => row.id === 'gone').name, '已移除的历史账号')
  assert.equal(rows.find(row => row.id === 'empty-brand').placeholder, true)
  assert.equal(rows.find(row => row.id === 'empty-brand').accountName, '暂无账号')
  assert.equal(arrangementTableRows(groupArrangementAccounts(options,cells)).find(row => row.id === 'empty-brand'), undefined)
  assert.equal(JSON.stringify(cells), before)
  const savedOnly = arrangementTableRows(groupArrangementAccounts(options,cells,{includeUnarranged:false,includeEmpty:false}))
  assert.deepEqual(new Set(savedOnly.map(row => row.id)), new Set(['parent','gone']))
})

test('每个账号提交载荷独立，空分类不会生成伪安排', () => {
  const rows = arrangementTableRows(groupArrangementAccounts({options:[]},[{platform_id:'one',platform_name:'账号一',remarks:'历史备注'}],{includeEmpty:false}))
  assert.equal(rows.length,1)
  const payload = arrangementCellPayload(rows[0].cell)
  assert.equal(payload.platform_id,'one')
  assert.equal(payload.remarks,'历史备注')
  assert.equal('category' in payload,false)
  assert.equal('parent_id' in payload,false)
})
