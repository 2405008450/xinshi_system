import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { sessionListKey } from '../src/utils/chatSessionList.js'

const source = readFileSync(new URL('../src/utils/chatSessionFolders.js', import.meta.url), 'utf8')
const defaults = JSON.parse(readFileSync(new URL('../../data/chat_session_folders.json', import.meta.url), 'utf8'))
const statusSource = readFileSync(new URL('../src/utils/annotationStatus.js', import.meta.url), 'utf8')
const { annotationStatusLabels, normalizeAnnotationStatus } = runInNewContext(statusSource.replaceAll('export ', '') + '\n;({annotationStatusLabels, normalizeAnnotationStatus})')
const api = runInNewContext(source.replace(/^import .*\r?\n/gm, '').replaceAll('export ', '') + '\n;({sessionFolderMentionUnread, sessionFolderNodes, sessionMatchesFolder, sessionFolderCount, assignableSessionFolders, annotationFolderId, resourceFolderId})', { defaults, annotationStatusLabels, normalizeAnnotationStatus, sessionListKey })

test('标注分组数量按主订单系列统计，与会话列表保持一致', () => {
  const sessions = ['AP-261007-001', 'AP-261007-001.001', 'AP-261007-001.001.001', 'AP-261007-002']
    .map((subtitle, index) => ({ key: `annotation:${index}`, projectType: 'annotation', subtitle }))
  assert.equal(api.sessionFolderCount(sessions, api.annotationFolderId, api.sessionFolderNodes()), 2)
})

test('默认五个一级分组、全部标注状态；六个资源讨论不是二级分类', () => {
  const nodes = api.sessionFolderNodes()
  assert.deepEqual(Array.from(nodes.filter(row => !row.parentKey), row => row.name), ['资源开拓讨论', '标注项目', '笔译项目', '口译项目', '招聘项目'])
  assert.equal(nodes.filter(row => row.parentKey === api.annotationFolderId).length, Object.keys(annotationStatusLabels).length)
  assert.equal(nodes.some(row => row.name === '平台讨论'), false)
  assert.equal(api.sessionMatchesFolder({ projectType: 'discussion' }, api.resourceFolderId, nodes), true)
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

test('资源分组下自定义讨论不再出现在分类树或会话归类选项', () => {
  const items = [{ id: 'room-a', parentKey: api.resourceFolderId, active: true, name: '新增讨论' }]
  assert.equal(api.sessionFolderNodes(items).some(row => row.id === 'room-a'), false)
  assert.equal(api.assignableSessionFolders(items).some(row => row.id === 'room-a'), false)
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
