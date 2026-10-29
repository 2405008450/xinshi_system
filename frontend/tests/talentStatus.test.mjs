import test from 'node:test'
import assert from 'node:assert/strict'
import { talentStatusOptions, talentStatusLabel } from '../src/utils/talentStatus.js'
import { reviewDisplay } from '../src/utils/talentDuplicateReview.js'

test('档案状态按指定顺序提供六项，各展示入口使用中文', () => {
  assert.deepEqual(talentStatusOptions.map(item => item.label), ['备用', '活跃', '休眠', '黑名单', '待激活', '待观察'])
  for (const { value, label } of talentStatusOptions) {
    assert.equal(talentStatusLabel(value), label)
    assert.equal(reviewDisplay(value), label)
  }
  assert.equal(talentStatusLabel('inactive'), '停用')
  assert.equal(talentStatusLabel(null), '-')
})
