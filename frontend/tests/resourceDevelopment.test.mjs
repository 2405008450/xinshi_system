import assert from 'node:assert/strict'
import test from 'node:test'
import { useDevelopmentFilters } from '../src/composables/useDevelopmentFilters.js'
import { developmentDateRange } from '../src/utils/resourceDevelopment.js'
import { recentDays, previousWorkday, cleanColumns, defaultDevelopmentColumns, continueDevelopmentValues, restoreDevelopmentBatch, progressText, progressStatuses } from '../src/utils/resourceDevelopment.js'
test('最近三天包含今天，跨月正确', () => { assert.deepEqual(recentDays(new Date(2026, 9, 1)), ['2026-09-29', '2026-10-01']) })
test('上一个工作日跳过周末', () => { assert.equal(previousWorkday(new Date(2026, 8, 28)), '2026-09-25'); assert.equal(previousWorkday(new Date(2026, 8, 27)), '2026-09-25') })
test('字段配置允许全部隐藏并过滤失效字段', () => { assert.deepEqual(cleanColumns([]), []); assert.deepEqual(cleanColumns(['removed', 'full_name']), ['full_name']); assert.deepEqual(cleanColumns({}), defaultDevelopmentColumns) })
test('连续录入仅保留四个批次字段，个人联系方式与状态不复用', () => {
  assert.deepEqual(continueDevelopmentValues({ platform_id: 'p', work_date: '2026-09-24', owner_id: 'u', account_id: 'a', full_name: '旧姓名', phone: '123', wechat: '旧微信', xiaohongshu: '旧小红书', actions: [{}] }), { platform_id: 'p', work_date: '2026-09-24', owner_id: 'u', account_id: 'a' })
})
test('独立进展显示日期和实际操作人员', () => {
  assert.equal(progressText({ progress: { group: { status: '已邀进群', action_date: '2026-09-09', operator_name: '宇琪' } } }, 'group'), '已拉群 · 09-09 · 宇琪')
  assert.equal(progressText({}, 'project'), '未处理')
  assert.equal(progressText({ progress: { wechat: { status: '已添加', action_date: null, operator_name: '原表未填写' } } }, 'wechat'), '已添加 · 原表未填日期 · 原表未填写')
  assert.deepEqual(progressStatuses('project'), ['未处理', '已入项'])
})
test('批次按当天及账号隔离，撤销代录权限后不沿用他人归属', () => {
  const options = { user_id: 'clerk', can_delegate: true, options: [{ id: 'p', kind: 'platform' }], users: [{ id: 'owner' }] }
  const saved = { user_id: 'clerk', day: '2026-09-24', batch: { platform_id: 'p', account_id: 'removed', owner_id: 'owner', work_date: '2026-09-23' } }
  assert.deepEqual(restoreDevelopmentBatch(saved, options, '2026-09-24'), { platform_id: 'p', owner_id: 'owner', work_date: '2026-09-23' })
  assert.deepEqual(restoreDevelopmentBatch(saved, options, '2026-09-25'), {})
  assert.deepEqual(restoreDevelopmentBatch(saved, { ...options, user_id: 'another' }, '2026-09-24'), {})
  assert.equal(restoreDevelopmentBatch(saved, { ...options, can_delegate: false }, '2026-09-24').owner_id, undefined)
})

import { hasNewPrivateEntry, defaultProgressStatus } from '../src/utils/resourceDevelopment.js'
test('私域入库只接受新增或修正成功状态，历史及日期修改不触发',()=>{
 const old=[{id:'a',channel:'wechat',status:'已添加',action_date:'2026-09-20'}]
 assert.equal(hasNewPrivateEntry(old,old),false)
 assert.equal(hasNewPrivateEntry([{...old[0],action_date:'2026-09-24'}],old),false)
 for(const [channel,status] of [['wechat','已添加'],['enterprise','已添加'],['group','已进群']]) assert.equal(hasNewPrivateEntry([...old,{id:'b',channel,status}],old),true)
 assert.equal(hasNewPrivateEntry([{id:'g',channel:'group',status:'已进群'}],[{id:'g',channel:'group',status:'已邀进群'}]),true)
 assert.equal(hasNewPrivateEntry([{id:'g',channel:'group',status:'已邀进群'}]),false)
 assert.equal(hasNewPrivateEntry([{id:'g',channel:'group',status:'已进群'},{id:'h',channel:'group',status:'未处理'}]),false)
 assert.equal(defaultProgressStatus('group'),'未处理')
 assert.deepEqual(progressStatuses('group'),['未处理','已拉群','已进群','已退群'])
})


import { sameDayRange, friendFollowUpOptions, developmentColumns } from '../src/utils/resourceDevelopment.js'
test('资源微信号与小红书号默认相邻，保留原有全部默认业务列', () => {
  assert.deepEqual(defaultDevelopmentColumns, [
    'platform_name', 'full_name', 'language_names', 'wechat', 'xiaohongshu', 'owner_name',
    'account_name', 'friend_accounts_text', 'wechat_status', 'enterprise_status', 'latest_follow_up',
    'group_status', 'group_large_status', 'communication_status', 'project_status',
  ])
  assert.deepEqual(developmentColumns.slice(2, 6).map(c => c.key), ['language_names', 'wechat', 'xiaohongshu', 'owner_name'])
})

test('升级联系方式新增前的默认列，保留自定义、全部隐藏和跨日日期列', () => {
  const old = defaultDevelopmentColumns.filter(key => !['wechat', 'xiaohongshu'].includes(key))
  for (const removed of [[], ['friend_accounts_text'], ['group_large_status'], ['friend_accounts_text', 'group_large_status']]) {
    const previous = old.filter(key => !removed.includes(key))
    assert.deepEqual(cleanColumns(previous), defaultDevelopmentColumns)
    assert.deepEqual(cleanColumns([...previous, 'work_date'], [...defaultDevelopmentColumns, 'work_date']), [...defaultDevelopmentColumns, 'work_date'])
  }
  assert.deepEqual(cleanColumns(['full_name', 'wechat', 'removed']), ['full_name', 'wechat'])
  assert.deepEqual(cleanColumns(['xiaohongshu']), ['xiaohongshu'])
  assert.deepEqual(cleanColumns([]), [])
})

test('同日日期工具，加微跟进在企微后，双渠道预设独立记录', () => {
  assert.deepEqual(sameDayRange(new Date(2026, 9, 6)), ['2026-10-06', '2026-10-06'])
  const keys = developmentColumns.map(c => c.key)
  assert.equal(keys.indexOf('latest_follow_up'), keys.indexOf('enterprise_status') + 1)
  assert.deepEqual(friendFollowUpOptions.find(p => p.label === '已添加微信和企微').channels, ['wechat', 'enterprise'])
  assert.equal(friendFollowUpOptions.find(p => p.label === '添加微信：二次请求').status, '二次请求')
  assert.equal(hasNewPrivateEntry([{id:'retry', channel:'wechat', status:'二次请求'}]), false)
})

test('微信企微状态顺序、快捷默认值与非成功状态入库保护', () => {
  const expected = ['未处理', '搜不到', '一次请求', '一次请求未通过', '二次请求', '二次请求未通过', '三次请求', '三次请求未通过', '已添加', '（对方）已删']
  for (const channel of ['wechat', 'enterprise']) {
    assert.deepEqual(progressStatuses(channel), expected)
    assert.equal(defaultProgressStatus(channel), '已添加')
    for (const status of expected.filter(s => s !== '已添加')) {
      assert.equal(hasNewPrivateEntry([{ id: status, channel, status }]), false)
    }
    for (const status of expected.slice(2).filter(s => s !== '已添加')) {
      assert.ok(friendFollowUpOptions.some(p => p.status === status && p.channels.includes(channel)))
    }
  }
  assert.equal(defaultProgressStatus('communication'), '已沟通')
  assert.equal(defaultProgressStatus('project'), '已入项')
})

test('两类企微群相邻、状态独立且仅已进群触发入库', () => {
  const keys = developmentColumns.map(column => column.key)
  assert.equal(keys.indexOf('group_large_status'), keys.indexOf('group_status') + 1)
  assert.ok(defaultDevelopmentColumns.includes('group_large_status'))
  assert.deepEqual(progressStatuses('group_large'), ['未处理', '已拉群', '已发码', '已进群', '已退群'])
  for (const channel of ['group', 'group_large']) {
    for (const status of progressStatuses(channel)) assert.equal(hasNewPrivateEntry([{ id: 'new', channel, status }]), status === '已进群')
  }
  assert.equal(hasNewPrivateEntry([{ id: 'a', channel: 'group', status: '已进群' }, { id: 'b', channel: 'group_large', status: '已退群' }]), true)
  assert.deepEqual(cleanColumns(defaultDevelopmentColumns.filter(key => key !== 'group_large_status')), defaultDevelopmentColumns)
  assert.deepEqual(cleanColumns(defaultDevelopmentColumns.filter(key => !['group_large_status', 'friend_accounts_text'].includes(key))), defaultDevelopmentColumns)
})

test('跨日期快捷范围含当天，本周从周一开始，过去一月固定30天', () => {
  const now = new Date('2026-10-08T04:00:00Z')
  for (const [key, range] of Object.entries({
    yesterday: ['2026-10-07', '2026-10-07'], week: ['2026-10-05', '2026-10-08'],
    lastWeek: ['2026-10-02', '2026-10-08'], month: ['2026-10-01', '2026-10-08'],
    lastMonth: ['2026-09-09', '2026-10-08'],
  })) assert.deepEqual(developmentDateRange(key, now), range)
})

test('快捷范围按香港日期计算并覆盖跨年、周日和闰月', () => {
  assert.deepEqual(developmentDateRange('yesterday', new Date('2025-12-31T16:05:00Z')), ['2025-12-31', '2025-12-31'])
  assert.deepEqual(developmentDateRange('week', new Date('2026-01-01T00:00:00Z')), ['2025-12-29', '2026-01-01'])
  assert.deepEqual(developmentDateRange('week', new Date('2026-10-11T04:00:00Z')), ['2026-10-05', '2026-10-11'])
  assert.deepEqual(developmentDateRange('lastWeek', new Date('2024-03-01T00:00:00Z')), ['2024-02-24', '2024-03-01'])
  assert.deepEqual(developmentDateRange('lastMonth', new Date('2024-03-01T00:00:00Z')), ['2024-02-01', '2024-03-01'])
})

test('按日列表与跨日筛选独立，组合参数与清空行为一致', () => {
  const main = useDevelopmentFilters(), dialog = useDevelopmentFilters()
  main.filters.keyword = '主页面'
  dialog.resetFilters('一次请求')
  Object.assign(dialog.filters, { range: ['2026-10-01', '2026-10-08'], platform_id: 'p', owner_id: 'u', account_id: 'a', keyword: '资源' })
  dialog.setColumnFilter('full_name', '姓名')
  assert.deepEqual(dialog.params(), {
    start: '2026-10-01', end: '2026-10-08', state: '一次请求', keyword: '资源',
    platform_id: 'p', owner_id: 'u', account_id: 'a', column_filters: '{"full_name":"姓名"}',
  })
  dialog.setColumnFilter('platform_name', ['p2'])
  assert.equal(dialog.filters.platform_id, '')
  dialog.filters.platform_id = 'p3'; dialog.clearCommonColumn('platform_id')
  assert.equal(dialog.columnFilters.platform_name, undefined)
  dialog.resetFilters()
  assert.deepEqual(dialog.params(), { start: undefined, end: undefined, column_filters: undefined })
  assert.equal(main.filters.keyword, '主页面')
})

test('跨日字段默认包含日期，允许全隐藏并清除过期字段', () => {
  const defaults = [...defaultDevelopmentColumns, 'work_date']
  assert.deepEqual(cleanColumns(null, defaults), defaults)
  assert.deepEqual(cleanColumns([], defaults), [])
  assert.deepEqual(cleanColumns(['work_date', 'removed'], defaults), ['work_date'])
})
