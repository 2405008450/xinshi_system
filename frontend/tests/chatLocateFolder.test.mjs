import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { locateConversationFolder } from '../src/utils/chatLocateFolder.js'
import { sessionListKey } from '../src/utils/chatSessionList.js'
import { PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType } from '../src/utils/projectStatus.js'

const folderSource = readFileSync(new URL('../src/utils/chatSessionFolders.js', import.meta.url), 'utf8')
const defaults = JSON.parse(readFileSync(new URL('../../data/chat_session_folders.json', import.meta.url), 'utf8'))
const companyChatRooms = JSON.parse(readFileSync(new URL('../../data/company_chat_rooms.json', import.meta.url), 'utf8'))
const statusSource = readFileSync(new URL('../src/utils/annotationStatus.js', import.meta.url), 'utf8')
const { annotationStatusLabels, normalizeAnnotationStatus } = runInNewContext(
  statusSource.replaceAll('export ', '') + '\n;({annotationStatusLabels, normalizeAnnotationStatus})',
)
const { sessionFolderNodes, annotationFolderId, resourceFolderId } = runInNewContext(
  folderSource.replace(/^import .*\r?\n/gm, '').replaceAll('export ', '')
  + '\n;({sessionFolderNodes, annotationFolderId, resourceFolderId})',
  { defaults, companyChatRooms, annotationStatusLabels, normalizeAnnotationStatus, sessionListKey, PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType },
)

const nodes = sessionFolderNodes([
  { id: 'folder-mgmt', name: '内部管理群', active: true },
  { id: 'room-biz', name: '口笔译业务', parentKey: 'folder-mgmt', active: true, isConversation: true },
  { id: 'cat-top', name: '2026年11月', parentKey: annotationFolderId, active: true },
  { id: 'cat-sub', name: '重点客户', parentKey: 'cat-top', active: true },
])

test('私聊会话不属于会话分组，快速定位返回空', () => {
  assert.equal(locateConversationFolder({ projectType: 'direct', projectId: 'u-1' }, nodes), '')
  assert.equal(locateConversationFolder({ kind: 'direct', projectId: 'u-2' }, nodes), '')
})

test('讨论群优先定位到分组树中的自身会话节点，其次资源开拓分组', () => {
  assert.equal(
    locateConversationFolder({ projectType: 'discussion', projectId: 'room-biz', title: '口笔译业务' }, nodes),
    'room-biz',
  )
  assert.equal(
    locateConversationFolder({ projectType: 'discussion', projectId: 'other-res', subtitle: '资源开拓讨论' }, nodes),
    resourceFolderId,
  )
})

test('标注项目有自定义分类时定位到最深自定义分类，否则定位到精准项目状态叶子节点', () => {
  assert.equal(
    locateConversationFolder({
      projectType: 'annotation',
      projectId: 'a-1',
      projectStatus: 'project_in_progress',
      categoryIds: ['cat-top', 'cat-sub'],
    }, nodes),
    'cat-sub',
  )
  assert.equal(
    locateConversationFolder({
      projectType: 'annotation',
      projectId: 'a-2',
      projectStatus: 'project_in_progress',
      categoryIds: [],
    }, nodes),
    'status:project_in_progress',
  )
  assert.equal(
    locateConversationFolder({
      projectType: 'annotation',
      projectId: 'a-2b',
      projectStatus: 'trialInProgress',
      categoryIds: [],
    }, nodes),
    'status:trial_in_progress',
  )
  assert.equal(
    locateConversationFolder({
      projectType: 'annotation',
      projectId: 'a-3',
      projectStatus: '',
      categoryIds: [],
    }, nodes),
    'status:__unset',
  )
})

test('笔译项目无自定义分类时定位到笔译模块下的精准状态节点，未知状态回退到模块一级分组', () => {
  assert.equal(
    locateConversationFolder({
      kind: 'translation',
      projectModule: 'translation',
      projectId: 't-1',
      projectStatus: 'sent_to_translator',
      categoryIds: [],
    }, nodes),
    'status:translation:sent_to_translator',
  )
  const translationRoot = nodes.find(row => !row.parentKey && row.ruleKey === 'translation').id
  assert.equal(
    locateConversationFolder({
      kind: 'translation',
      projectModule: 'translation',
      projectId: 't-2',
      projectStatus: 'legacy_unknown_status',
      categoryIds: [],
    }, nodes),
    translationRoot,
  )
})

test('会话分组主入口、历史列表辅助入口与工作区右键菜单已完整接入', () => {
  const treeSource = readFileSync(new URL('../src/components/chat/ChatSessionFolderTree.vue', import.meta.url), 'utf8')
  const historySource = readFileSync(new URL('../src/components/chat/ChatSessionHistory.vue', import.meta.url), 'utf8')
  const workspaceSource = readFileSync(new URL('../src/components/chat/ChatWorkspace.vue', import.meta.url), 'utf8')

  assert.match(treeSource, /@click="emit\('locate-active'\)"/)
  assert.match(treeSource, /<Aim\s*\/>/)
  assert.match(treeSource, /async function reveal\(id = props\.selected, \{ expand = false, flash = false \} = \{\}\)/)
  assert.match(treeSource, /archivedExpanded\.value = nextArchived/)
  assert.match(treeSource, /is-locate-flash/)

  assert.match(historySource, /defineEmits\(\['open', 'locate'\]\)/)
  assert.match(historySource, /v-if="item\.kind !== 'direct'"/)
  assert.match(historySource, /\$emit\('locate', \{ \.\.\.item, projectType: item\.kind \}\)/)

  assert.match(workspaceSource, /@locate-active="locateActiveConversation"/)
  assert.match(workspaceSource, /@locate="locateSessionInFolders"/)
  assert.match(workspaceSource, /v-if="canLocateSession\(sessionMenuSession\)"[^>]*@click="runLocateSession\(sessionMenuSession\)"/)
  assert.match(workspaceSource, /folderTreeRef\.value\?\.reveal\(target, \{ expand: true, flash: true \}\)/)
})
