import { dateText, newDevelopmentId, progressChannels } from './resourceDevelopment.js'

export const entryFields = [
  { key: 'platform_id', label: '开拓平台', type: 'platform', required: true, width: 170 },
  { key: 'work_date', label: '开拓日期', type: 'date', required: true, width: 160 },
  { key: 'owner_id', label: '开拓人员', type: 'owner', required: true, width: 150 },
  { key: 'account_id', label: '交换账号', type: 'account', width: 160 },
  { key: 'friend_accounts', label: '加微账号', type: 'friends', width: 200 },
  { key: 'full_name', label: '资源姓名', required: true, width: 170, max: 255 },
  { key: 'language_ids', label: '语种/方言', type: 'languages', width: 220 },
  { key: 'phone', label: '资源手机', width: 170, max: 100 },
  { key: 'whatsapp', label: '资源 WhatsApp 号', width: 180, max: 100 },
  { key: 'wechat', label: '资源微信号', width: 170, max: 100 },
  { key: 'xiaohongshu', label: '资源小红书号', width: 170, max: 100 },
  { key: 'custom_accounts', label: '自定义资源账号', type: 'custom', width: 340 },
  { key: '_statuses', label: '跟进进展', type: 'statuses', width: 240 },
  { key: 'capabilities', label: '专业分类/查重关联', type: 'enrollment', width: 250 },
  { key: 'follow_up_content', label: '后续跟进情况', type: 'textarea', width: 240, max: 20000 },
  { key: 'remarks', label: '备注', type: 'textarea', width: 240, max: 20000 },
]
export const capabilityOptions = [{ value: 'written_translation', label: '笔译' }, { value: 'interpretation', label: '口译' }, { value: 'annotation', label: '标注' }, { value: 'recruitment', label: '全职' }]
export function newEntryRow(options, template = {}, now = new Date()) {
  const row = {
    platform_id: '', work_date: dateText(now), owner_id: options.user_id, account_id: null,
    friend_accounts: [], full_name: '', language_ids: [], phone: '', whatsapp: '', wechat: '', xiaohongshu: '',
    custom_accounts: [], custom_fields: {}, capabilities: [], link_person_id: null, duplicate_note: '', follow_up_content: '', remarks: '',
    _statuses: Object.fromEntries(Object.keys(progressChannels).map(channel => [channel, ''])),
    ...JSON.parse(JSON.stringify(template)),
  }
  return { ...row, id: newDevelopmentId(), revision: 0, link_person_id: null, _error: '', _candidates: [],
    _followupId: newDevelopmentId(), _actionIds: Object.fromEntries(Object.keys(progressChannels).map(channel => [channel, newDevelopmentId()])) }
}
export const entryNeedsEnrollment = row => Object.entries(row._statuses).some(([channel, status]) => ({ wechat: '已添加', enterprise: '已添加', group: '已进群', group_large: '已进群' })[channel] === status && !!status)
export function entryPayload(row) {
  return {
    ...Object.fromEntries(['id', 'revision', 'platform_id', 'work_date', 'owner_id', 'account_id', 'friend_accounts', 'full_name', 'language_ids', 'phone', 'whatsapp', 'wechat', 'xiaohongshu', 'custom_accounts', 'custom_fields', 'capabilities', 'link_person_id', 'duplicate_note', 'remarks'].map(key => [key, row[key]])),
    actions: Object.entries(row._statuses).filter(([, status]) => status).map(([channel, status]) => ({ id: row._actionIds[channel], channel, status, action_date: row.work_date, operator_id: row.owner_id, account_id: row.account_id })),
    follow_ups: row.follow_up_content.trim() ? [{ id: row._followupId, content: row.follow_up_content.trim() }] : [],
  }
}
