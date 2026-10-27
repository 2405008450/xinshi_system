import test from 'node:test'
import assert from 'node:assert/strict'
import { discussionMessagePayload } from '../src/utils/discussionMessagePayload.js'

test('普通讨论消息不提交本地候选人员状态', () => {
  assert.deepEqual(discussionMessagePayload({content:'测试',clientMessageId:'retry-id',selectedUsers:[]}), {
    content:'测试',clientMessageId:'retry-id',replyToId:null,mentionedUserIds:[],mentionAll:false,
  })
})
test('@人员、@所有人和引用保留业务字段；旧失败草稿重试保持幂等编号并移除多余字段', () => {
  const oldDraft = {content:'@所有人 请查看',clientMessageId:'same-id',replyToId:'123',mentionedUserIds:['member'],mentionAll:true,selectedUsers:[{id:'__all__',name:'所有人'}]}
  const payload = discussionMessagePayload(oldDraft)
  assert.deepEqual(payload,{content:oldDraft.content,clientMessageId:'same-id',replyToId:'123',mentionedUserIds:['member'],mentionAll:true})
  assert.deepEqual(discussionMessagePayload(payload),payload)
  assert.equal(oldDraft.selectedUsers.length,1)
})
