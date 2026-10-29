import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretationRatingOptions, interpretationRatingLabel, interpretationRatingHint } from '../src/utils/talentPerformance.js'

test('口译星级一至六星且未评定不显示虚构等级', () => {
  assert.deepEqual(interpretationRatingOptions.map(item => item.label), ['一星', '二星', '三星', '四星', '五星', '六星'])
  assert.deepEqual(interpretationRatingOptions.map(item => item.value), [1, 2, 3, 4, 5, 6])
  assert.equal(interpretationRatingLabel(4), '四星')
  assert.equal(interpretationRatingLabel(null), '-')
  assert.equal(interpretationRatingHint, '四星以上为可担任大型会议交传与同传')
})
