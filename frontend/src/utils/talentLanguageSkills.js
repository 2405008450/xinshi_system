// 0 表示原文未明确顺序；加载、显示及保存都不能替用户推定第一外语。
export function normalizeForeignLanguagePriorities(skills) {
  return skills.map(skill => {
    if (skill.role !== 'foreign') return { ...skill }
    const value = skill.priority
    const numeric = typeof value === 'number' || (typeof value === 'string' && /^\d+$/.test(value))
    const priority = numeric && Number.isInteger(Number(value)) && Number(value) >= 0 && Number(value) <= 9 ? Number(value) : 0
    return { ...skill, priority }
  })
}

export function languageRoleLabel(item) {
  if (item.role === 'native') return '母语'
  if (item.role !== 'foreign') return '方言/民族语言'
  const priority = normalizeForeignLanguagePriorities([item])[0].priority
  return priority ? `第${priority}外语` : '外语（顺序未明确）'
}
