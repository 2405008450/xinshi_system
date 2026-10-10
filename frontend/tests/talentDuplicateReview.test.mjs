import test from 'node:test'
import assert from 'node:assert/strict'
import { buildReviewPayload, selectedFieldState, reviewDisplay } from '../src/utils/talentDuplicateReview.js'

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
