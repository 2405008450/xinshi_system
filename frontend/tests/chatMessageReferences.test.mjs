import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(`../src/components/${path}`, import.meta.url), 'utf8')

test('点击消息气泡与气泡内引用摘要不再直接弹出引用关系窗口，仅保留操作栏入口', () => {
  const discussion = read('chat/DiscussionConversation.vue')
  const timeline = read('chat/ChatTimeline.vue')
  const panel = read('ProjectChatPanel.vue')
  const actions = read('chat/ChatMessageActions.vue')

  assert.doesNotMatch(discussion, /openMessageReferences/)
  assert.doesNotMatch(discussion, /<blockquote[^>]*@click=/)
  assert.doesNotMatch(timeline, /openReferences/)
  assert.doesNotMatch(timeline, /class="group-reply"[^>]*@click/)
  assert.doesNotMatch(panel, /openMessageReferences/)
  assert.doesNotMatch(panel, /class="group-reply"[^>]*@click/)

  assert.match(actions, /@click="\$emit\('references',\s*message\.id,\s*\$event\)"/)
  assert.match(actions, /查看引用/)
})

test('消息引用关系卡片复用普通消息与 @ 消息的背景填充与高亮样式', () => {
  const dialog = read('chat/ChatMessageReferences.vue')
  const branch = read('chat/ChatReferenceBranch.vue')

  assert.match(dialog, /:current-user-id="currentUserId"/)
  assert.match(dialog, /var\(--chat-stage-bg,\s*#f4f6f9\)/)
  assert.match(branch, /is-own':\s*isOwn/)
  assert.match(branch, /is-mentioned':\s*isMentioned/)
  assert.match(branch, /var\(--chat-bubble-bg,\s*#ffffff\)/)
  assert.match(branch, /var\(--chat-bubble-own-bg,\s*#e3ecf6\)/)
  assert.match(branch, /var\(--chat-bubble-mention-bg,\s*#fef9ec\)/)
  assert.match(branch, /var\(--chat-bubble-mention-accent,\s*#d97706\)/)
  assert.match(branch, /mentionParts/)
  assert.match(branch, /undisplayedMentions/)
})
