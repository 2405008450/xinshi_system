import { reactive } from 'vue'
export const DEPARTMENT_NAMES = reactive([
  '项目经理',
  'IT部',
  '项目部',
  '客户部',
  'HR部',
  '排版',
  '其他',
  '销售'
])

const DEPARTMENT_ALIASES = reactive({
  招聘项目: '其他',
  翻译部: 'IT部'
})

const revisions = new Map()
export function applyDepartmentCatalog(data) {
  if (!data?.ready) return
  if (data.items.some(item => (revisions.get(item.id) || 0) > item.revision)) return
  for (const item of data.items) revisions.set(item.id,item.revision)
  DEPARTMENT_NAMES.splice(0, DEPARTMENT_NAMES.length, ...data.items.map(item => item.name))
  for (const key of Object.keys(DEPARTMENT_ALIASES)) delete DEPARTMENT_ALIASES[key]
  Object.assign(DEPARTMENT_ALIASES, data.aliases || {})
}

export function normalizeDepartment(value) {
  const normalized = String(value || '').trim()
  return DEPARTMENT_ALIASES[normalized] || normalized
}
