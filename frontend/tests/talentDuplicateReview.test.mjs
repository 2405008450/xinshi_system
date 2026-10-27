import test from 'node:test'
import assert from 'node:assert/strict'
import { buildReviewPayload, selectedFieldState, reviewDisplay, crossDecisionPairs, validateIdentityDraft, pairRelation } from '../src/utils/talentDuplicateReview.js'

test('只处理选择的成员，字段决策路径和散列保持原样', () => {
  const decisions = { 'written_profile.languages': { person_id: 'b' }, 'language_skills:hash': { person_id: 'a', value_hash: 'hash' } }
  assert.deepEqual(buildReviewPayload('merge', ['a', 'b'], 'a', decisions), { action: 'merge', person_ids: ['a', 'b'], target_id: 'a', decisions, note: '' })
  assert.equal(buildReviewPayload('different', ['a', 'b'], 'a').target_id, null)
})
test('互补、冲突、缺失分别展示，零和否不是缺失', () => {
  assert.equal(selectedFieldState([null, '北京']), 'complement')
  assert.equal(selectedFieldState(['男', '女']), 'conflict')
  assert.equal(selectedFieldState([null, []]), 'missing')
  assert.equal(selectedFieldState([0, 0]), 'same')
  assert.equal(selectedFieldState([false, null]), 'complement')
})
test('语言角色、状态与多行原文清晰展示', () => {
  assert.match(reviewDisplay({ role: 'native', proficiency: 'familiar' }), /母语.*熟悉/)
  assert.equal(reviewDisplay(['第一来源', '第二来源']), '第一来源\n第二来源')
  assert.equal(reviewDisplay(null), '-')
})

test('只区分子组之间的交叉关系，不区分组内重复档案', () => {
  const pairs = crossDecisionPairs(['a','b'],['c','d'])
  assert.deepEqual(pairs,[['a','c'],['a','d'],['b','c'],['b','d']])
  const payload = buildReviewPayload('different',['a','b','c','d'],null,{},'',{ decisionPairs:pairs })
  assert.deepEqual(payload.decision_pairs,pairs)
  assert.throws(() => crossDecisionPairs(['a','b'],['b','c']), /互不重叠/)
})

test('草稿子组不能重叠，人工关系优先于 Agent 建议', () => {
  const drafts = [{ id:'1',person_ids:['a','b'] },{ id:'2',person_ids:['c','d'] }]
  assert.match(validateIdentityDraft(['b','e'],drafts), /不能进入两个/)
  assert.equal(validateIdentityDraft(['a','e'],drafts,'1'),'')
  assert.match(validateIdentityDraft(['a'],drafts,'1'), /至少需要两条/)
  assert.equal(pairRelation({decision:'different'},{classification:'same',confidence:'high'}).label,'已确认不同人')
  assert.equal(pairRelation({identity_conflicts:['出生日期不同']},{classification:'same',confidence:'high'}).type,'danger')
})
