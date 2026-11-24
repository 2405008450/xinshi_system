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
const entryChannels = Object.keys(progressChannels)
const entryArrayFields = ['friend_accounts', 'language_ids', 'custom_accounts', 'capabilities', '_candidates']
const isEntryObject = value => value != null && typeof value === 'object' && !Array.isArray(value)
const hasEntryId = value => typeof value === 'string' && value.length > 0

export function newEntryRow(options, template = {}, now = new Date()) {
  const { _statuses, ...fields } = JSON.parse(JSON.stringify(template))
  const row = {
    platform_id: '', work_date: dateText(now), owner_id: options.user_id, account_id: null,
    friend_accounts: [], full_name: '', language_ids: [], phone: '', whatsapp: '', wechat: '', xiaohongshu: '',
    custom_accounts: [], custom_fields: {}, capabilities: [], link_person_id: null, duplicate_note: '', follow_up_content: '', remarks: '',
    ...fields,
    _statuses: Object.fromEntries(entryChannels.map(channel => [channel, _statuses?.[channel] ?? ''])),
  }
  return { ...row, id: newDevelopmentId(), revision: 0, link_person_id: null, _error: '', _candidates: [],
    _followupId: newDevelopmentId(), _actionIds: Object.fromEntries(entryChannels.map(channel => [channel, newDevelopmentId()])) }
}

export function restoreEntryRow(options, snapshot) {
  if (!isEntryObject(snapshot)) return newEntryRow(options)
  if (isEntryObject(snapshot._statuses) && isEntryObject(snapshot._actionIds) && isEntryObject(snapshot.custom_fields)
    && hasEntryId(snapshot.id) && hasEntryId(snapshot._followupId)
    && entryChannels.every(channel => typeof snapshot._statuses[channel] === 'string' && hasEntryId(snapshot._actionIds[channel]))
    && entryArrayFields.every(key => Array.isArray(snapshot[key]))
    && typeof snapshot.follow_up_content === 'string' && typeof snapshot.duplicate_note === 'string') return snapshot

  const restored = newEntryRow(options, snapshot)
  // 草稿可能来自旧版；只补齐缺失结构，已有请求标识用于避免重试时重复新增。
  for (const key of ['id', '_followupId']) {
    if (hasEntryId(snapshot[key])) restored[key] = snapshot[key]
  }
  for (const channel of entryChannels) {
    if (hasEntryId(snapshot._actionIds?.[channel])) restored._actionIds[channel] = snapshot._actionIds[channel]
  }
  for (const key of entryArrayFields) restored[key] = Array.isArray(snapshot[key]) ? snapshot[key] : []
  restored.custom_fields = isEntryObject(snapshot.custom_fields) ? snapshot.custom_fields : {}
  restored.follow_up_content = typeof snapshot.follow_up_content === 'string' ? snapshot.follow_up_content : ''
  restored.duplicate_note = typeof snapshot.duplicate_note === 'string' ? snapshot.duplicate_note : ''
  restored.link_person_id = snapshot.link_person_id ?? null
  restored._error = snapshot._error ?? ''
  return restored
}

export const entryNeedsEnrollment = row => Object.entries(row._statuses).some(([channel, status]) => ({ wechat: '已添加', enterprise: '已添加', group: '已进群', group_large: '已进群' })[channel] === status && !!status)
export function entryPayload(row) {
  return {
    ...Object.fromEntries(['id', 'revision', 'platform_id', 'work_date', 'owner_id', 'account_id', 'friend_accounts', 'full_name', 'language_ids', 'phone', 'whatsapp', 'wechat', 'xiaohongshu', 'custom_accounts', 'custom_fields', 'capabilities', 'link_person_id', 'duplicate_note', 'remarks'].map(key => [key, row[key]])),
    actions: Object.entries(row._statuses).filter(([, status]) => status).map(([channel, status]) => ({ id: row._actionIds[channel], channel, status, action_date: row.work_date, operator_id: row.owner_id, account_id: row.account_id })),
    follow_ups: row.follow_up_content.trim() ? [{ id: row._followupId, content: row.follow_up_content.trim() }] : [],
  }
}

export async function saveEntryRow(api, row, options) {
  let payload = entryPayload(row)
  let saved
  let conflict = false
  try { saved = await api.save(payload) }
  catch (error) {
    if (error.rawDetail?.code !== 'creation_id_conflict') throw error
    conflict = true
  }
  // 兼容尚未升级的后端：旧接口会把不同内容的同 UUID 请求误报为保存成功。
  const matches = saved && ['id', 'platform_id', 'work_date', 'owner_id', 'full_name']
    .every(key => saved[key] === (typeof payload[key] === 'string' ? payload[key].trim() : payload[key]))
  if (matches) return saved
  if (!conflict && (!saved || saved.id !== payload.id || !saved.revision ||
    !['platform_id', 'work_date', 'owner_id', 'full_name'].every(key => typeof saved[key] === 'string'))) {
    throw new Error('保存响应异常，填写内容已保留，请重新查询后重试')
  }
  const fresh = newEntryRow(options, row)
  Object.assign(row, { id: fresh.id, _actionIds: fresh._actionIds, _followupId: fresh._followupId })
  payload = entryPayload(row)
  // 新标识在行内保留；第二次请求超时后继续用同一标识重试，避免重复新增。
  saved = await api.save(payload)
  if (!saved || !['id', 'platform_id', 'work_date', 'owner_id', 'full_name']
    .every(key => saved[key] === (typeof payload[key] === 'string' ? payload[key].trim() : payload[key]))) {
    throw new Error('保存结果与填写内容不一致，填写内容已保留，请重新查询后重试')
  }
  return saved
}
