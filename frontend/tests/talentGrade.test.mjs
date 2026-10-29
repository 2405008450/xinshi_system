import test from 'node:test'
import assert from 'node:assert/strict'
import { talentGradeOptions, talentGradeLabel } from '../src/utils/talentGrade.js'
import { reviewDisplay } from '../src/utils/talentDuplicateReview.js'

test('人才分级选项及历史未评定档案展示', () => {
  assert.deepEqual(talentGradeOptions.map(item => item.label), ['S', 'A', 'B', 'C', '待评定'])
  for (const grade of ['S', 'A', 'B', 'C']) assert.equal(talentGradeLabel(grade), grade)
  for (const value of [null, undefined, '', 'pending']) assert.equal(talentGradeLabel(value), '待评定')
  assert.equal(reviewDisplay('pending'), '待评定')
})
