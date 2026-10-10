export const reviewStateLabels = { pending: '待核对', different: '已区分', deferred: '暂缓处理' }
export const fieldStateLabels = { same: '相同', complement: '互补', conflict: '冲突', missing: '缺失' }
export const actionLabels = { different: '确认不同人', defer: '暂缓处理', keep: '保留一条', merge: '合并资料' }
const labels = {
  native: '母语', foreign: '外语', dialect_ethnic: '方言／民族语言',
  active: '活跃', standby: '备用', inactive: '停用',
  written_translation: '笔译', interpretation: '口译', annotation: '标注',
  very_familiar: '非常熟悉', familiar: '熟悉', basic: '基础交流', listening_mainly: '听懂为主', listening_only: '仅能听懂',
  high: '高', medium: '中', low: '低', male: '男', female: '女',
}
const keys = { role: '类型', proficiency: '熟悉程度', language_id: '语种', language_label: '语种', language_display: '语种', priority: '顺序',
  capability_type: '能力', status: '状态', review_required: '待核重', remarks: '备注', institution: '院校', major: '专业',
  graduation_year: '毕业年份', education_level: '学历', name: '名称', issuer: '发证机构', certificate_no: '证书编号',
  material_received: '已收到材料', source_language_id: '源语种', target_language_id: '目标语种',
  source_language_label: '源语种', target_language_label: '目标语种', display: '语言方向',
  certificate_type: '证书类型', issued_on: '颁发日期', institution_category: '院校分类', major_category: '专业分类',
  minor_major: '辅修专业', degree_name: '学位名称' }
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
export function buildReviewPayload(action, personIds, targetId, decisions = {}, note = '') {
  return { action, person_ids: [...personIds], target_id: ['keep', 'merge'].includes(action) ? targetId : null, decisions, note }
}
