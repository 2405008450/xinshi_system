// 编辑其他项目资料时不重复提交客户经理，只有明确调整才进入经理变更流程。
export function projectClientManagerPayload(form, baselineId, creating = false) {
  const managerId = String(form.clientManagerId || '').trim()
  if (!creating && managerId === String(baselineId || '').trim()) return {}
  return {
    clientManagerId: managerId || null,
    clientManagerChangeReason: String(form.clientManagerChangeReason || '').trim() || null,
  }
}
