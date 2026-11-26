import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { sessionListKey } from '../src/utils/chatSessionList.js'

const source = readFileSync(new URL('../src/utils/chatSessionFolders.js', import.meta.url), 'utf8')
const defaults = JSON.parse(readFileSync(new URL('../../data/chat_session_folders.json', import.meta.url), 'utf8'))
const companyChatRooms = JSON.parse(readFileSync(new URL('../../data/company_chat_rooms.json', import.meta.url), 'utf8'))
const statusSource = readFileSync(new URL('../src/utils/annotationStatus.js', import.meta.url), 'utf8')
const { annotationStatusLabels, normalizeAnnotationStatus } = runInNewContext(statusSource.replaceAll('export ', '') + '\n;({annotationStatusLabels, normalizeAnnotationStatus})')
const projectStatusSource = readFileSync(new URL('../src/utils/projectStatus.js', import.meta.url), 'utf8')
const { PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType } = runInNewContext(projectStatusSource.replaceAll('export ', '') + '\n;({PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType})')
const api = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replaceAll('export ', '') + '\n;({annotationFolderEntries, sessionFolderMentionUnread, sessionFolderNodes, sessionMatchesFolder, sessionFolderCount, assignableSessionFolders, annotationFolderId, resourceFolderId, placeCompanyConversations})', { defaults, companyChatRooms, annotationStatusLabels, normalizeAnnotationStatus, sessionListKey, PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType })

test('默认顺序是全体大群、内部管理群、资源开拓、各业务项目', () => {
  const roots=[{id:'other'},{id:'interpretation',ruleKey:'interpretation'}, {id:'resource',name:'资源开拓与讨论'}, {id:'all',name:'（全体大群）',isConversation:true}, {id:'internal',name:'内部管理群'}, {id:api.resourceFolderId}, {id:'annotation',ruleKey:'annotation'}, {id:'translation',ruleKey:'translation'}]
  assert.deepEqual(Array.from(api.placeCompanyConversations(roots),row=>row.id), ['all','internal',api.resourceFolderId,'annotation','translation','interpretation','other','resource'])
})

test('技术开发分组和所属会话按部门授权显示并汇总',()=>{
  const root=defaults.find(row=>row.ruleKey==='technical').id
  const rows=[{id:'tech-task',name:'开发任务',parentKey:root,active:true,isConversation:true},{id:'tech-general',name:'技术/开发沟通',parentKey:root,active:true,isConversation:true,fixedTop:true}]
  assert.equal(api.sessionFolderNodes(rows).some(row=>[root,'tech-task','tech-general'].includes(row.id)),false)
  const nodes=api.sessionFolderNodes(rows,{technicalAccess:true})
  assert.equal(nodes.filter(row=>[root,'tech-task','tech-general'].includes(row.id)).length,3)
  const sessions=rows.map(row=>({key:`discussion:${row.id}`,projectType:'discussion',categoryIds:[row.id]}))
  assert.equal(api.sessionFolderCount(sessions,root,nodes),2)
  assert.equal(api.sessionMatchesFolder(sessions[0],api.annotationFolderId,nodes),false)
})

test('二级分类下会话可见，数量与未读汇总到分类及一级分组，停用分类隐藏后代', () => {
  const root = defaults.find(row => row.ruleKey === 'translation').id
  const folder = {id:'folder',name:'业务分类',parentKey:root,active:true}
  const room = {id:'room',name:'分类内会话',parentKey:'folder',active:true,isConversation:true}
  const nodes = api.sessionFolderNodes([folder,room])
  const sessions = [{key:'discussion:room',projectType:'discussion',subtitle:'群聊',categoryIds:['room'],mentionUnread:2}]
  assert.equal(nodes.some(row=>row.id==='room'),true)
  for(const id of [root,'folder','room']) {
    assert.equal(api.sessionFolderCount(sessions,id,nodes),1)
    assert.equal(api.sessionFolderMentionUnread(sessions,id,nodes),2)
  }
  assert.equal(api.sessionFolderNodes([{...folder,active:false},room]).some(row=>row.id==='room'),false)
})

test('标注分组数量按主订单系列统计，与会话列表保持一致', () => {
  const sessions = ['AP-261007-001', 'AP-261007-001.001', 'AP-261007-001.001.001', 'AP-261007-002']
    .map((subtitle, index) => ({ key: `annotation:${index}`, projectType: 'annotation', subtitle }))
  assert.equal(api.sessionFolderCount(sessions, api.annotationFolderId, api.sessionFolderNodes()), 2)
})

test('默认五个一级分组、各模块状态目录及六个资源会话', () => {
  const nodes = api.sessionFolderNodes()
  assert.deepEqual(Array.from(nodes.filter(row => !row.parentKey), row => row.name), ['资源开拓与讨论', '标注项目', '笔译项目', '口译项目', '招聘项目'])
  assert.equal(nodes.filter(row => row.parentKey === 'status-root:annotation').length, Object.keys(annotationStatusLabels).length + 1)
  assert.equal(nodes.some(row => row.name === '平台讨论'), true)
  assert.equal(api.sessionMatchesFolder({ projectType: 'discussion', subtitle:'资源开拓讨论' }, api.resourceFolderId, nodes), true)
})

test('自建群聊只显示于所属分组，不混入资源讨论', () => {
  const parent = defaults.find(row => row.ruleKey === 'translation').id
  const nodes = api.sessionFolderNodes([{ id: 'room', name: '企业管理', parentKey: parent, active: true, isConversation: true }])
  const session = { key: 'discussion:room', projectType: 'discussion', subtitle: '群聊', categoryIds: ['room'] }
  assert.equal(api.sessionMatchesFolder(session, parent, nodes), true)
  assert.equal(api.sessionMatchesFolder(session, 'room', nodes), true)
  assert.equal(api.sessionMatchesFolder(session, api.resourceFolderId, nodes), false)
})

test('按业务类型和当前状态自动归类，兼容历史驼峰值', () => {
  const nodes = api.sessionFolderNodes()
  const session = { projectType: 'annotation', projectStatus: 'projectInProgress' }
  assert.equal(api.sessionMatchesFolder(session, api.annotationFolderId, nodes), true)
  assert.equal(api.sessionMatchesFolder(session, 'status:project_in_progress', nodes), true)
  assert.equal(api.sessionMatchesFolder(session, 'status:trial_preparation', nodes), false)
  assert.equal(api.sessionMatchesFolder(session, defaults[2].id, nodes), false)
})

test('自定义二级关联可在一级汇总，停用父目录后不再展示子目录', () => {
  const items = [{ id: 'root', name: '自定义', active: true }, { id: 'child', name: '平台A', active: true, parentKey: 'root' }]
  const session = { projectType: 'translation', categoryIds: ['child'] }
  assert.equal(api.sessionMatchesFolder(session, 'root', api.sessionFolderNodes(items)), true)
  assert.equal(api.sessionMatchesFolder(session, 'child', api.sessionFolderNodes(items)), true)
  assert.equal(api.sessionMatchesFolder(session, 'unknown', api.sessionFolderNodes(items)), false)
  items[0].active = false
  assert.equal(api.sessionFolderNodes(items).some(row => row.id === 'child'), false)
})

test('手动归类选项显示完整路径，自动状态不能手动修改', () => {
  const options = api.assignableSessionFolders([{ id: 'c', name: '重点', active: true, parentKey: api.annotationFolderId }])
  assert.equal(options.find(row => row.id === 'c').label, '标注项目 / 重点')
  assert.equal(options.some(row => row.id.startsWith('status:')), false)
  assert.equal(options.some(row => row.id === defaults[5].id), false)
})

test('二级分类数量按授权会话去重统计，状态改变后数量同步，不计私聊', () => {
  const rows = [
    { key: 'annotation:1', projectType: 'annotation', projectStatus: 'project_in_progress' },
    { key: 'annotation:1', projectType: 'annotation', projectStatus: 'project_in_progress', opened: true },
    { key: 'annotation:2', projectType: 'annotation', projectStatus: 'trial_preparation' },
    { key: 'direct:3', projectType: 'direct', projectStatus: 'project_in_progress' },
  ]
  const nodes = api.sessionFolderNodes()
  assert.equal(api.sessionFolderCount(rows, 'status:project_in_progress', nodes), 1)
  assert.equal(api.sessionFolderCount(rows, 'status:trial_preparation', nodes), 1)
  assert.equal(api.sessionFolderCount(rows, api.annotationFolderId, nodes), 2)
  rows[2].projectStatus = 'project_in_progress'
  assert.equal(api.sessionFolderCount(rows, 'status:project_in_progress', nodes), 2)
  assert.equal(api.sessionFolderCount(rows, 'status:trial_preparation', nodes), 0)
})

test('资源目录支持自定义会话和正常的父级汇总', () => {
  const items = [{ id: 'room-a', parentKey: api.resourceFolderId, active: true, name: '新增讨论' }]
  assert.equal(api.sessionFolderNodes(items).some(row => row.id === 'room-a'), true)
  assert.equal(api.assignableSessionFolders(items).some(row => row.id === 'room-a'), true)
})


test('未读提及数字汇总到父分组及状态分组，同一订单重复出现只统计一次', () => {
  const nodes = api.sessionFolderNodes([])
  const rows = [
    {key:'a', projectType:'annotation', projectStatus:'trial_preparation', mentionUnread:2},
    {key:'a', projectType:'annotation', projectStatus:'trial_preparation', mentionUnread:2},
    {key:'b', projectType:'annotation', projectStatus:'trial_preparation', mentionUnread:3},
    {key:'c', projectType:'annotation', projectStatus:'client_feedback', mentionUnread:1},
    {key:'d', projectType:'direct', mentionUnread:9},
  ]
  assert.equal(api.sessionFolderMentionUnread(rows, api.annotationFolderId, nodes), 6)
  assert.equal(api.sessionFolderMentionUnread(rows, 'status:trial_preparation', nodes), 5)
  assert.equal(api.sessionFolderMentionUnread(rows, api.resourceFolderId, nodes), 0)
})


test('一级会话与一级目录平级，按自身会话汇总数量与提及', () => {
  const room = {id:'root-room',name:'一级会话',parentKey:null,active:true,isConversation:true}
  const folder = {id:'root-folder',name:'一级目录',parentKey:null,active:true}
  const nodes = api.sessionFolderNodes([room,folder])
  assert.equal(nodes.find(row=>row.id===room.id).parentKey,null)
  assert.equal(nodes.find(row=>row.id===room.id).isConversation,true)
  const sessions = [{key:'discussion:root-room',projectType:'discussion',subtitle:'群聊',categoryIds:[room.id],mentionUnread:2}]
  assert.equal(api.sessionFolderCount(sessions,room.id,nodes),1)
  assert.equal(api.sessionFolderMentionUnread(sessions,room.id,nodes),2)
  assert.equal(api.sessionFolderCount(sessions,folder.id,nodes),0)
})


test('标注通用讨论固定在技术需求总入口之前，其他项目会话保持原顺序', () => {
  const rows = [{id:'status'}, {id:'tech-room', name:'技术需求 · 项目甲', isConversation:true}, {id:'general', name:'标注通用讨论', isConversation:true}]
  const entries = api.annotationFolderEntries(rows, api.annotationFolderId)
  assert.deepEqual(Array.from(entries, row=>row.id), ['general','annotation-technical-picker','status','tech-room'])
  assert.equal(entries[1].isTechnicalEntry, true)
  assert.equal(api.annotationFolderEntries(rows, api.resourceFolderId), rows)
})


test('四个模块的项目状态与日期平级，并且管理讨论固定第一、状态固定第二', () => {
  for (const module of ['annotation','translation','interpretation','recruitment']) {
    const root=defaults.find(row=>row.ruleKey===module).id
    const name={annotation:'标注通用讨论',translation:'笔译项目管理讨论',interpretation:'口译项目管理讨论',recruitment:'招聘项目管理讨论'}[module]
    const nodes=api.sessionFolderNodes([{id:'date',name:'261126',parentKey:root,active:true},{id:'manage',name,isConversation:true,parentKey:root,active:true}])
    const entries=api.annotationFolderEntries(nodes.filter(row=>row.parentKey===root).reverse(),root)
    assert.equal(entries[0].id,'manage');assert.equal(entries[1].id,`status-root:${module}`)
    assert.ok(nodes.filter(row=>row.parentKey===`status-root:${module}`).every(row=>!!row.statusIcon))
    const key=PROJECT_STATUS_OPTIONS[module][0].value
    const session={key:'discussion:opened',projectType:'discussion',projectModule:module,projectStatus:key,categoryIds:['date']}
    assert.equal(api.sessionMatchesFolder(session,'date',nodes),true)
    const status=module==='annotation'?`status:${key}`:`status:${module}:${key}`
    assert.equal(api.sessionMatchesFolder(session,status,nodes),true)
    assert.equal(api.sessionMatchesFolder(session,`status-root:${module}`,nodes),true)
    assert.equal(api.sessionFolderCount([session,session],root,nodes),1)
  }
  const nodes=api.sessionFolderNodes([{id:'legacy',name:'通用标注',isConversation:true,active:true},{id:'keep',name:'标注通用讨论',parentKey:api.annotationFolderId,isConversation:true,active:true}])
  assert.equal(nodes.some(row=>row.id==='legacy'),false);assert.equal(nodes.some(row=>row.id==='keep'),true)
})


test('资源开拓与讨论为正常目录，按会话归属匹配，Facebook 使用推广图标', () => {
  const nodes=api.sessionFolderNodes([{id:'facebook',name:'Facebook小红书',parentKey:api.resourceFolderId,active:true,isConversation:true}])
  assert.equal(nodes.find(row=>row.id===api.resourceFolderId).name,'资源开拓与讨论')
  assert.equal(nodes.find(row=>row.id==='facebook').conversationIcon,'Promotion')
  assert.equal(api.sessionMatchesFolder({kind:'discussion',categoryIds:['facebook']},api.resourceFolderId,nodes),true)
  assert.equal(api.sessionMatchesFolder({kind:'discussion',categoryIds:['other-room']},api.resourceFolderId,nodes),false)
  assert.ok(nodes.filter(row=>row.parentKey===api.resourceFolderId&&row.isConversation).every(row=>!!row.conversationIcon))
})
