// 保留已有的有效顺序，只为未设置或重复的外语补上可用序号。
export function normalizeForeignLanguagePriorities(skills) {
  const used = new Set()
  return skills.map(skill => {
    if (skill.role !== 'foreign') return { ...skill }
    let priority = Number(skill.priority)
    if (!Number.isInteger(priority) || priority < 1 || priority > 9 || used.has(priority)) {
      priority = 1
      while (used.has(priority) && priority < 9) priority += 1
    }
    used.add(priority)
    return { ...skill, priority }
  })
}
