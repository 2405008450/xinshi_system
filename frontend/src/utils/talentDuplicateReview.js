import { talentStatusLabels } from './talentStatus.js'
import { talentGradeOptions } from './talentGrade.js'
import { contactAvailabilityOptions } from './talentContactAvailability.js'

export const reviewStateLabels = { pending: '待核对', different: '已区分', deferred: '暂缓处理' }
export const fieldStateLabels = { same: '相同', complement: '互补', conflict: '冲突', missing: '缺失' }
export const actionLabels = { different: '确认不同人', defer: '暂缓处理', keep: '保留一条', merge: '合并资料' }
const labels = {
  native: '母语', foreign: '外语', dialect_ethnic: '方言／民族语言',
  ...talentStatusLabels,
  ...Object.fromEntries(talentGradeOptions.map(item => [item.value, item.label])),
  ...Object.fromEntries(contactAvailabilityOptions.map(item => [item.value, item.label])),
  written_translation: '笔译', interpretation: '口译', annotation: '标注',
  very_familiar: '非常熟悉', familiar: '熟悉', basic: '基础交流', listening_mainly: '听懂为主', listening_only: '仅能听懂',
  high: '高', medium: '中', low: '低', male: '男', female: '女',
  resume: '简历', certificate: '证书',
}
const keys = { role: '类型', proficiency: '熟悉程度', language_id: '语种', language_label: '语种', language_display: '语种', priority: '顺序',
  capability_type: '能力', status: '状态', review_required: '待核重', remarks: '备注', institution: '院校', major: '专业',
  graduation_year: '毕业年份', education_level: '学历', name: '名称', issuer: '发证机构', certificate_no: '证书编号',
  material_received: '已收到材料', source_language_id: '源语种', target_language_id: '目标语种',
  source_language_label: '源语种', target_language_label: '目标语种', display: '语言方向',
  certificate_type: '证书类型', issued_on: '颁发日期', institution_category: '院校分类', major_category: '专业分类',
  minor_major: '辅修专业', degree_name: '学位名称', readonly: '只读', category: '材料类别' }
export function reviewDisplay(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.length ? value.map(reviewDisplay).join('\n') : '-'
  if (typeof value === 'object') return Object.entries(value)
    .filter(([key, item]) => !['id', 'person_id', 'created_at', 'updated_at', 'sort_order'].includes(key) && item !== null && item !== '' &&
      !(key === 'language_id' && value.language_label) && !(key === 'source_language_id' && value.source_language_label) && !(key === 'target_language_id' && value.target_language_label))
    .map(([key, item]) => `${keys[key] || key}：${reviewDisplay(item)}`).join('；')
  return labels[value] || String(value)
}
export function selectedFieldState(values) {
  const nonempty = values.filter(value => value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length))
  if (!nonempty.length) return 'missing'
  if (new Set(nonempty.map(value => JSON.stringify(value))).size > 1) return 'conflict'
  return nonempty.length === values.length ? 'same' : 'complement'
}
export function buildReviewPayload(action, personIds, targetId, decisions = {}, note = '', context = {}) {
  return { action, person_ids: [...personIds], target_id: ['keep', 'merge'].includes(action) ? targetId : null, decisions, note,
    ...(context.decisionPairs ? { decision_pairs: context.decisionPairs } : {}),
    ...(context.reportId ? { agent_report_id: context.reportId } : {}) }
}

export function crossDecisionPairs(left, right) {
  if (!left.length || !right.length || new Set([...left, ...right]).size !== left.length + right.length) throw new Error('请选择两个互不重叠的子组')
  return left.flatMap(a => right.map(b => [a, b]))
}

export function validateIdentityDraft(ids, drafts, editingId = null) {
  if (ids.length < 2 || new Set(ids).size !== ids.length) return '一个合并子组至少需要两条不同档案'
  if (drafts.some(group => group.id !== editingId && group.person_ids.some(id => ids.includes(id)))) return '同一档案不能进入两个准备提交的子组，请先调整原子组'
  return ''
}

export function pairRelation(pair, suggestion) {
  if (pair?.decision === 'different') return { label: '已确认不同人', type: 'info' }
  if (pair?.decision === 'defer') return { label: '已暂缓', type: 'warning' }
  if (pair?.identity_conflicts?.length) return { label: '身份冲突', type: 'danger' }
  if (!suggestion) return { label: '待初筛', type: 'info' }
  const level = { high: '高', medium: '中', low: '低' }[suggestion.confidence]
  return { label: `${{ same: '疑似同一人', different: '疑似不同人', uncertain: '证据不足' }[suggestion.classification]}·${level}`,
    type: suggestion.classification === 'same' && suggestion.confidence === 'high' ? 'success' : 'warning' }
}
