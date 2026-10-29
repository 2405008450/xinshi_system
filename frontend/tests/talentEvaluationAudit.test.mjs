import test from 'node:test'
import assert from 'node:assert/strict'
import { evaluationSnapshot, evaluationGroupMeta } from '../src/utils/talentEvaluationAudit.js'

test('评价快照保留分区并归一化空白，不引用可变表单', () => {
  const form={overallScore:8,overallRating:'  合格  ',writtenProfile:{qualityScore:'优秀'}}
  const before=evaluationSnapshot(form)
  form.overallScore=9
  assert.equal(before.overall.overallScore,8)
  assert.equal(before.overall.overallRating,'合格')
  assert.equal(before.written_profile['writtenProfile.qualityScore'],'优秀')
  assert.equal(before.collection.collectionScore,null)
})

test('评价元信息兼容接口的递归 camelCase 转换', () => {
  const meta={actorAccount:'actual-account',createdAt:'2026-10-29T12:00:00+08:00'}
  assert.equal(evaluationGroupMeta({evaluationMeta:{audioAnnotation:meta}},'audio_annotation'),meta)
  assert.equal(evaluationGroupMeta({},'overall'),undefined)
})
