import test from 'node:test'
import assert from 'node:assert/strict'
import { cleanTeamColumns, defaultTeamColumns, emptyTeam, emptyTeamFilters, teamDisplay, teamParams, teamPayload, teamContactSummary, emptyTeamContact, cleanTeamContacts } from '../src/utils/teamResources.js'

test('团队字段配置过滤旧键，允许全部取消且不改变默认配置', () => {
  assert.deepEqual(cleanTeamColumns(['unknown', 'short_name', 'short_name']), ['short_name'])
  assert.deepEqual(cleanTeamColumns([]), [])
  assert.throws(() => cleanTeamColumns({}))
  assert.equal(defaultTeamColumns.length, 9)
  assert.deepEqual(cleanTeamColumns(defaultTeamColumns.filter(key => !['contacts', 'attachment_count'].includes(key))), defaultTeamColumns)
  assert.deepEqual(cleanTeamColumns(defaultTeamColumns.filter(key => key !== 'attachment_count')), defaultTeamColumns)
  assert.equal(teamDisplay({ attachment_count: 2 }, 'attachment_count', {}), '2 个附件')
})
test('联系人按稳定标识提交，受限用户不回传脱敏联系方式', () => {
  const contacts = [emptyTeamContact(), { id: 'saved-id', name: ' 张三 ', nickname: ' 小张 ', contact_info: '******' }]
  assert.deepEqual(cleanTeamContacts(contacts, false), [{ id: 'saved-id', name: '张三', nickname: '小张' }])
  const result = teamPayload({ ...emptyTeam(), contacts }, false)
  assert.equal(result.contacts[0].contact_info, undefined)
  assert.equal(teamContactSummary(result.contacts), '张三')
  assert.equal(teamContactSummary([...result.contacts, { nickname: '小李' }]), '张三 等2人')
  assert.equal(teamDisplay({ contacts: [] }, 'contacts', {}), '-')
})
test('表单只提交业务字段并清理其他说明与空人员', () => {
  const result = teamPayload({ ...emptyTeam(), resource_types: ['annotation', 'annotation'], other_resource_description: '旧说明', contact_user_id: '', created_at: '旧时间' })
  assert.deepEqual(result.resource_types, ['annotation'])
  assert.equal(result.other_resource_description, '')
  assert.equal(result.contact_user_id, null)
  assert.equal(result.created_at, undefined)
  assert.equal(teamPayload({ ...result, resource_types: ['other'], other_resource_description: '采集' }).other_resource_description, '采集')
})
test('统一构建分页与全部组合查询条件', () => {
  const filters = { ...emptyTeamFilters(), keyword: ' 全称 ', team_type: 'small_team', resource_types: ['annotation', 'interpretation'], contact_user_id: 'person', follow_up_user_id: 'person2', contact_dates: ['2026-10-01', '2026-10-12'] }
  assert.deepEqual(teamParams(filters, 2, 20), { skip: 20, limit: 20, keyword: '全称', team_type: 'small_team', resource_types: ['annotation', 'interpretation'], contact_user_id: 'person', follow_up_user_id: 'person2', contact_start: '2026-10-01', contact_end: '2026-10-12' })
  assert.deepEqual(teamParams(emptyTeamFilters(), 1, 20), { skip: 0, limit: 20 })
})
test('日期与时间跨浏览器时区仍按香港展示，纯文本保留换行', () => {
  const options = { team_types: [], resource_types: [{ value: 'annotation', label: '标注' }] }
  assert.equal(teamDisplay({ contact_date: '2026-10-12' }, 'contact_date', options), '2026年10月12日')
  assert.equal(teamDisplay({ resource_types: ['annotation'] }, 'resource_types', options), '标注')
  assert.equal(teamDisplay({ introduction: '一\n二' }, 'introduction', options), '一\n二')
  assert.equal(teamDisplay({ contact_user: { name: '张三', is_active: false } }, 'contact_user', options), '张三（已停用）')
  assert.equal(teamDisplay({ updated_at: '2026-10-11T16:05:00Z' }, 'updated_at', options), teamDisplay({ updated_at: '2026-10-12T00:05:00+08:00' }, 'updated_at', options))
})
