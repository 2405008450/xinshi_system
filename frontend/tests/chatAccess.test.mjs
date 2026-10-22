import test from 'node:test'
import assert from 'node:assert/strict'
import { chatConversationScope } from '../src/utils/chatAccess.js'

test('访问校验识别各类会话主接口，拒绝后可以准确关闭对应窗口', () => {
  const id = '11111111-1111-4111-8111-111111111111'
  for (const [url, projectType] of [
    [`/project-chat/annotation/${id}/start`, 'annotation'],
    [`/project-chat/${id}/messages?skip=0`, 'translation'],
    [`/chat/discussions/${id}/messages`, 'discussion'],
    [`/chat/direct/${id}/group`, 'direct'],
  ]) assert.deepEqual(chatConversationScope(url), { projectType, projectId: id })
  for (const url of ['/project-chat/annotation/default-participants', `/project-chat/annotation/${id}/files/missing`, '/chat/users']) assert.equal(chatConversationScope(url), null)
})
