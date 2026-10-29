import test from 'node:test'
import assert from 'node:assert/strict'
import { talentTimezoneOptions } from '../src/utils/talentTimezones.js'
import { contactAvailabilityOptions, contactAvailabilityLabel } from '../src/utils/talentContactAvailability.js'

test('所在地时区涵盖半小时、45分钟偏移，零时区和边界无重复', () => {
  const values = talentTimezoneOptions.map(item => item.value)
  assert.equal(new Set(values).size, values.length)
  assert.equal(values[0], 'UTC-12')
  assert.equal(values.at(-1), 'UTC+14')
  for (const value of ['UTC+0', 'UTC+8', 'UTC+5:30', 'UTC+5:45', 'UTC-3:30']) assert.ok(values.includes(value))
})

test('可联系时段枚举能正确展示并兼容空记录', () => {
  assert.equal(contactAvailabilityOptions.length, 7)
  assert.equal(contactAvailabilityLabel('evening'), '晚间')
  assert.equal(contactAvailabilityLabel('appointment'), '需提前预约')
  assert.equal(contactAvailabilityLabel(null), '-')
})
