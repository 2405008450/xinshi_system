import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')

test('useChatMentions 透传 sender_id 参数并返回聚合提及人列表', () => {
  const composable = read('composables/useChatMentions.js')
  assert.match(composable, /sender_id:\s*filters\.value\.senderId\s*\|\|\s*undefined/)
  assert.match(composable, /if\s*\(Array\.isArray\(data\.senders\)\)\s*senders\.value\s*=\s*data\.senders/)
  assert.match(composable, /return\s*\{\s*items,\s*senders,/)
})

test('会话面板在注册分组提及人的监听前初始化会话模式', () => {
  const workspace = read('components/chat/ChatWorkspace.vue')
  // Vue 注册监听时会立即读取启用条件，此时会话模式必须已有初始值。
  assert.match(workspace, /const annotationMode = ref\('group'\)[\s\S]*?const scopedMentionSenders = useChatMentionSenders\(/)
})

test('@我 收件箱、分组内 @我 与分组筛选支持按具体提及人下钻，且不在会话分组树多造一级假分组', () => {
  const inbox = read('components/chat/ChatMentionInbox.vue')
  const tree = read('components/chat/ChatSessionFolderTree.vue')
  const workspace = read('components/chat/ChatWorkspace.vue')

  assert.match(inbox, /按提及人筛选/)
  assert.match(inbox, /emit\('select-sender'/)
  assert.doesNotMatch(tree, /__mention_senders__/)
  assert.doesNotMatch(tree, /@我 · 按提及人/)
  assert.match(workspace, /useChatMentionSenders/)
  assert.match(workspace, /filterMentionExpanded/)
  assert.match(workspace, /scopedMentionSenders/)
  assert.match(workspace, /senderId:\s*selectedMentionSender\.value\s*\|\|\s*undefined/)
})
