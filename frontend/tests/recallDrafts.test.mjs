import test from 'node:test'
import assert from 'node:assert/strict'
import { captureRecallDraft, combineRecallDraft, createRecallDraftStore, recallDraftKey } from '../src/utils/recallDrafts.js'

const message = (extra = {}) => ({ id: 'message', senderUserId: 'owner', messageType: 'user', content: '@同事 原内容', mentions: [{ mentionedUserId: 'person', mentionedUserName: '同事' }], ...extra })
const storage = () => { const rows = new Map(); return { getItem: key => rows.get(key), setItem: (key, value) => rows.set(key, value) } }

test('四类会话独立保存，刷新后可恢复，账号与会话之间互不串稿', async () => {
  const local = storage(), store = createRecallDraftStore(local)
  for (const kind of ['annotation', 'direct', 'translation', 'discussion']) {
    const key = recallDraftKey('owner', kind, 'same-id')
    await store.remember(key, message({ content: kind }), 'owner')
    assert.equal((await createRecallDraftStore(local).restore(key, 'message', 'owner')).content, kind)
    assert.equal(await store.restore(key, 'message', 'other'), null)
    assert.equal(await store.restore(recallDraftKey('owner', kind, 'other-id'), 'message', 'owner'), null)
  }
})

test('仅本人普通消息可保存，撤回提示和别人消息不产生原文副本', () => {
  assert.equal(captureRecallDraft(message({ senderUserId: 'other' }), 'owner'), null)
  assert.equal(captureRecallDraft(message({ recalledAt: '2026-10-29T10:00:00+08:00' }), 'owner'), null)
  assert.equal(captureRecallDraft(message({ messageType: 'handover' }), 'owner'), null)
  assert.equal(captureRecallDraft(message({ content: '' }), 'owner'), null)
})

test('恢复合并当前草稿，保留富文本、@与引用，保护字数和提及人数限制', () => {
  const recovered = captureRecallDraft(message({ contentJson: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '@同事 原内容', marks: [{ type: 'bold' }] }] }] }, reply: { id: 'quoted' } }), 'owner')
  const result = combineRecallDraft({ content: '已有草稿', mentionIds: ['already'] }, recovered)
  assert.equal(result.content, '已有草稿\n@同事 原内容')
  assert.deepEqual(result.mentionIds, ['already', 'person'])
  assert.deepEqual(result.contentJson.content[1].content[0].marks, [{ type: 'bold' }])
  assert.equal(result.replyTo.id, 'quoted')
  assert.throws(() => combineRecallDraft({ content: 'a'.repeat(10000) }, recovered), /10000/)
  assert.throws(() => combineRecallDraft({ content: '', mentionIds: Array.from({ length: 20 }, (_, index) => String(index)) }, recovered), /20人/)
})

test('@所有人恢复为群体提及，不把展开后的全体名单变成超过20位的单独提及', () => {
  const recovered = captureRecallDraft(message({ metadata: { mentionAll: true } }), 'owner')
  assert.deepEqual(combineRecallDraft({ content: '' }, recovered).mentionIds, ['__all__'])
})

test('附件恢复使用文件副本，重新编辑后移除旧副本；存储不可写时当前页面仍可恢复', async () => {
  const store = createRecallDraftStore(storage()), key = recallDraftKey('owner', 'direct', 'files')
  await store.remember(key, message({ attachments: [{ id: 'old', originalName: 'original.txt', contentType: 'text/plain' }] }), 'owner', async () => new Blob(['attachment content']))
  const recovered = await store.restore(key, 'message', 'owner')
  assert.equal(recovered.files[0].name, 'original.txt')
  assert.equal(await recovered.files[0].text(), 'attachment content')
  store.remove(key, 'message')
  assert.equal(await store.restore(key, 'message', 'owner'), null)
  const blocked = createRecallDraftStore({ getItem: () => null, setItem: () => { throw Error('quota') } })
  await blocked.remember('blocked-isolated', message(), 'owner')
  assert.equal((await blocked.restore('blocked-isolated', 'message', 'owner')).content, '@同事 原内容')
})
