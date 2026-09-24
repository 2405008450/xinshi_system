import assert from 'node:assert/strict'
import test from 'node:test'
import { recentDays, previousWorkday, cleanColumns, defaultDevelopmentColumns, continueDevelopmentValues, restoreDevelopmentBatch, progressText, progressStatuses } from '../src/utils/resourceDevelopment.js'
test('最近三天包含今天，跨月正确', () => { assert.deepEqual(recentDays(new Date(2026, 9, 1)), ['2026-09-29', '2026-10-01']) })
test('上一个工作日跳过周末', () => { assert.equal(previousWorkday(new Date(2026, 8, 28)), '2026-09-25'); assert.equal(previousWorkday(new Date(2026, 8, 27)), '2026-09-25') })
test('字段配置允许全部隐藏并过滤失效字段', () => { assert.deepEqual(cleanColumns([]), []); assert.deepEqual(cleanColumns(['removed', 'full_name']), ['full_name']); assert.deepEqual(cleanColumns({}), defaultDevelopmentColumns) })
test('连续录入仅保留四个批次字段，个人联系方式与状态不复用', () => {
  assert.deepEqual(continueDevelopmentValues({ platform_id: 'p', work_date: '2026-09-24', owner_id: 'u', account_id: 'a', full_name: '旧姓名', phone: '123', actions: [{}] }), { platform_id: 'p', work_date: '2026-09-24', owner_id: 'u', account_id: 'a' })
})
test('独立进展显示日期和实际操作人员', () => {
  assert.equal(progressText({ progress: { group: { status: '已邀进群', action_date: '2026-09-09', operator_name: '宇琪' } } }, 'group'), '已邀进群 · 09-09 · 宇琪')
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
