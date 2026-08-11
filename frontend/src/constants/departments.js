export const DEPARTMENT_NAMES = [
  '项目经理',
  'IT部',
  '项目部',
  '客户部',
  'HR部',
  '排版',
  '其他',
  '销售'
]

const DEPARTMENT_ALIASES = {
  招聘项目: '其他',
  翻译部: 'IT部'
}

export function normalizeDepartment(value) {
  const normalized = String(value || '').trim()
  return DEPARTMENT_ALIASES[normalized] || normalized
}
