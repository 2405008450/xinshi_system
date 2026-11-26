import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import {
  createOptimisticMessage,
  isOptimisticMessage,
  mergeWithOptimistic,
} from '../src/utils/chatOptimistic.js'
import { sessionListKey } from '../src/utils/chatSessionList.js'
import { PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType } from '../src/utils/projectStatus.js'

const folderSource = readFileSync(new URL('../src/utils/chatSessionFolders.js', import.meta.url), 'utf8')
const defaults = JSON.parse(readFileSync(new URL('../../data/chat_session_folders.json', import.meta.url), 'utf8'))
const companyChatRooms = JSON.parse(readFileSync(new URL('../../data/company_chat_rooms.json', import.meta.url), 'utf8'))
const statusSource = readFileSync(new URL('../src/utils/annotationStatus.js', import.meta.url), 'utf8')
const { annotationStatusLabels, normalizeAnnotationStatus } = runInNewContext(statusSource.replaceAll('export ', '') + '\n;({annotationStatusLabels, normalizeAnnotationStatus})')
const {
  createSessionFolderIndex,
  sessionFolderCount,
  sessionFolderMentionUnread,
  sessionFolderNodes,
  annotationFolderId,
  resourceFolderId,
} = runInNewContext(
  folderSource.replace(/^import .*\r?\n/gm, '').replaceAll('export ', '') + '\n;({createSessionFolderIndex, sessionFolderCount, sessionFolderMentionUnread, sessionFolderNodes, annotationFolderId, resourceFolderId})',
  { defaults, companyChatRooms, annotationStatusLabels, normalizeAnnotationStatus, sessionListKey, PROJECT_STATUS_OPTIONS, normalizeProjectStatus, getProjectStatusType },
)

test('乐观消息排在真实消息之后，讨论群 BigInt 排序不会报错', () => {
  const real1 = { id: '100', content: 'first' }
  const real2 = { id: '200', content: 'second' }
  const opt1 = createOptimisticMessage({ clientMessageId: 'cid-1', senderUserId: 'u1', content: 'hi 1' })
  const opt2 = createOptimisticMessage({ clientMessageId: 'cid-2', senderUserId: 'u1', content: 'hi 2' })

  const compareBigInt = (a, b) => (BigInt(a.id) < BigInt(b.id) ? -1 : BigInt(a.id) > BigInt(b.id) ? 1 : 0)
  const merged = mergeWithOptimistic([real2, opt2, real1], [opt1], { compareReal: compareBigInt })

  assert.deepEqual(merged.map(m => m.id), ['100', '200', opt1.id, opt2.id])
  assert.equal(isOptimisticMessage(opt1), true)
  assert.equal(isOptimisticMessage(real1), false)
})

test('真实消息到达时可通过 replaceTempId 或 clientMessageId 自动替换乐观消息且不重复', () => {
  const opt1 = createOptimisticMessage({ clientMessageId: 'cid-a', senderUserId: 'u1', content: 'hello' })
  const opt2 = createOptimisticMessage({ clientMessageId: 'cid-b', senderUserId: 'u1', content: 'world' })
  const compareSeq = (a, b) => (a.sequenceNo || 0) - (b.sequenceNo || 0)

  // 通过 clientMessageId 去重（如 WebSocket 先于 HTTP 返回推送）
  const wsMsg = { id: 'srv-1', sequenceNo: 10, clientMessageId: 'cid-a', content: 'hello' }
  const afterWs = mergeWithOptimistic([opt1, opt2], [wsMsg], { compareReal: compareSeq })
  assert.deepEqual(afterWs.map(m => m.id), ['srv-1', opt2.id])

  // 通过 replaceTempId 精确替换
  const httpMsg = { id: 'srv-2', sequenceNo: 11, content: 'world' }
  const afterHttp = mergeWithOptimistic(afterWs, [httpMsg], { replaceTempId: opt2.id, compareReal: compareSeq })
  assert.deepEqual(afterHttp.map(m => m.id), ['srv-1', 'srv-2'])
})

test('createSessionFolderIndex 与原有计数函数结果完全一致', () => {
  const custom = [
    { id: 'f-date-1', name: '2026-11-25', parentKey: annotationFolderId, active: true },
    { id: 'f-date-2', name: '2026-11-26', parentKey: annotationFolderId, active: true },
  ]
  const nodes = sessionFolderNodes(custom, { technicalAccess: true })
  const sessions = [
    { key: 'annotation:1', projectId: '1', projectType: 'annotation', projectStatus: '进行中', categoryIds: ['f-date-1'], mentionUnread: 2 },
    { key: 'annotation:2', projectId: '2', projectType: 'annotation', projectStatus: '已完成', categoryIds: ['f-date-2'], mentionUnread: 1 },
    { key: 'direct:u2', projectId: 'u2', projectType: 'direct', mentionUnread: 5 },
    { key: 'discussion:r1', projectId: 'r1', projectType: 'discussion', subtitle: '资源开拓讨论', mentionUnread: 3 },
  ]

  const index = createSessionFolderIndex(sessions, nodes)
  for (const node of nodes) {
    assert.equal(index.counts.get(node.id) || 0, sessionFolderCount(sessions, node.id, nodes), `count mismatch for ${node.id}`)
    assert.equal(index.mentionUnreads.get(node.id) || 0, sessionFolderMentionUnread(sessions, node.id, nodes), `mention mismatch for ${node.id}`)
  }
  assert.equal(index.counts.get(annotationFolderId), 2)
  assert.equal(index.mentionUnreads.get(annotationFolderId), 3)
  assert.equal(index.counts.get(resourceFolderId), 1)
})

test('ChatMessageActions 不再渲染已读统计加载中占位文案且对乐观消息隐藏', () => {
  const source = readFileSync(new URL('../src/components/chat/ChatMessageActions.vue', import.meta.url), 'utf8')
  assert.equal(source.includes('已读统计加载中'), false)
  assert.match(source, /!message\.optimisticStatus/)
})
