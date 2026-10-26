export function managedProjectFilters(serialized, mine, userId) {
  if (!mine) return serialized
  const filters = serialized ? JSON.parse(serialized) : {}
  // 登录态缺失时也不回退成全部项目。
  filters.managed_user_id = { op: 'in', value: [userId || '00000000-0000-0000-0000-000000000000'] }
  return JSON.stringify(filters)
}
