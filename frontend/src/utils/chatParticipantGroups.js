import { matchesSearch } from './searchMatching.js'

// 名册只补充部门信息，可邀请范围始终以会话接口为准。
export function participantGroups(users, members, directory = {}, keyword = '') {
  const memberIds = new Set(members.map(person => String(person.id)))
  const people = new Map((directory.people || []).map(person => [String(person.id), person]))
  const aliases = directory.aliases || {}, groups = new Map(), seen = new Set()
  for (const person of users) {
    const id = String(person.id)
    if (memberIds.has(id) || seen.has(id)) continue
    seen.add(id)
    const entry = people.get(id)
    const names = [...new Set([...(entry?.departments || []).map(dept => dept.name), entry?.primaryDepartment || person.department].filter(Boolean).map(name => aliases[name] || name))]
    if (!matchesSearch([person.name, entry?.username, ...names].join(' '), keyword)) continue
    for (const name of names.length ? names : ['未分配部门']) {
      if (!groups.has(name)) groups.set(name, [])
      groups.get(name).push(person)
    }
  }
  const order = (directory.items || []).map(dept => dept.name)
  return [...groups].sort(([a], [b]) => {
    if (a === '未分配部门') return 1
    if (b === '未分配部门') return -1
    const rank = name => order.includes(name) ? order.indexOf(name) : order.length
    return rank(a) - rank(b) || a.localeCompare(b, 'zh-CN')
  }).map(([name, people]) => ({ name, people }))
}
export function toggleParticipantSelection(selected, people, checked) {
  const values = new Map(selected.map(id => [String(id), id]))
  for (const person of people) {
    if (checked) values.set(String(person.id), person.id)
    else values.delete(String(person.id))
  }
  return [...values.values()]
}
