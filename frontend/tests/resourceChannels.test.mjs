import test from 'node:test'
import assert from 'node:assert/strict'
import { cleanChannelColumns, channelMembersText, channelParams, defaultChannelColumns } from '../src/utils/resourceChannels.js'

test('渠道字段配置保留全取消并过滤过时字段和重复键', () => {
  assert.deepEqual(cleanChannelColumns([]), [])
  assert.deepEqual(cleanChannelColumns(['name', 'unknown', 'name', 'users']), ['name', 'users'])
  assert.throws(() => cleanChannelColumns({ name: true }))
  assert.deepEqual(defaultChannelColumns, ['name', 'category', 'purpose', 'maintainers', 'users'])
})

test('人员展示区分停用人员和空值', () => {
  assert.equal(channelMembersText([]), '-')
  assert.equal(channelMembersText([{ name: '甲', is_active: true }, { name: '乙', is_active: false }]), '甲、乙（已停用）')
})

test('列表和总数共用筛选参数，保留多选人员并正确分页', () => {
  const filters = { keyword: ' 用途 ', category: 'local', maintainer_ids: ['a', 'b'], user_ids: ['c'] }
  const params = channelParams(filters, 3, 20)
  assert.deepEqual(params, { keyword: '用途', category: 'local', maintainer_ids: ['a', 'b'], user_ids: ['c'], skip: 40, limit: 20 })
  filters.maintainer_ids.push('d')
  assert.deepEqual(params.maintainer_ids, ['a', 'b'])
  assert.equal(channelParams({ keyword: '', category: '', maintainer_ids: [], user_ids: [] }, 1, 10).keyword, undefined)
})
