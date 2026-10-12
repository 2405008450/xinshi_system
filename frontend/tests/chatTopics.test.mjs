import assert from 'node:assert/strict'
import test from 'node:test'
import { orderedTopicRoots, topicSearchParams, messageTopicPatch } from '../src/utils/chatTopics.js'

test('模块排序仅调整入口，不改动团队数据或包含停用菜单', () => {
  const rows = [{id:'a',builtin_key:'annotation',active:true,sort_order:10,name:'标注项目'}, {id:'b',builtin_key:'resource-development',active:true,sort_order:20,name:'资源开拓讨论'}, {id:'c',active:false,sort_order:0,name:'停用'}, {id:'d',parent_id:'b',active:true,sort_order:0,name:'子菜单'}]
  assert.deepEqual(orderedTopicRoots(rows, 'resource').map(x=>x.id), ['b','a'])
  assert.deepEqual(orderedTopicRoots(rows, 'annotation').map(x=>x.id), ['a','b'])
  assert.equal(rows[0].id, 'a')
})
test('跨会话查询不残留当前会话条件，分页保留相同主题', () => {
  const common = {topicId:'topic',projectId:'project',projectType:'direct',keyword:'  高校  ',before:123}
  const current = topicSearchParams({...common,scope:'current'})
  const all = topicSearchParams({...common,scope:'all'})
  assert.equal(current.conversation_id,'project')
  assert.equal(all.conversation_id,undefined)
  assert.equal(all.conversation_type,undefined)
  assert.equal(all.before,123)
  assert.equal(all.keyword,'高校')
  assert.equal(all.topic_id,'topic')
})
test('分类清除仍保留修订号用于并发保护', () => {
  assert.deepEqual(messageTopicPatch({topic_id:null,topic_path:null,topic_revision:2,can_classify:true}), {topicId:null,topicPath:null,topicRevision:2,canClassify:true})
})
