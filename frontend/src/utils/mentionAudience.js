import { matchesSearch } from './searchMatching.js'

// 默认只显示群内人员；主动展开或搜索时才展示可邀请人员。
export function mentionAudience(members, invitable, { query = '', expanded = false, currentUserId = '', selected = [] } = {}) {
  const seen = new Set([String(currentUserId)]), selectedIds = new Set(selected.map(String))
  const rows = [{ id: '__all__', name: '所有人', full_name: '所有人', all: true, outside: false }]
  for (const [people, outside] of [[members, false], [invitable, true]]) {
    for (const person of people) {
      const id = String(person.id)
      if (seen.has(id)) continue
      seen.add(id)
      if (outside && !expanded && !query.trim() && !selectedIds.has(id)) continue
      rows.push({ ...person, name: person.name || person.full_name || person.username, outside })
    }
  }
  return rows.filter(person => matchesSearch([person.name, person.full_name, person.username].filter(Boolean).join(' '), query))
}
