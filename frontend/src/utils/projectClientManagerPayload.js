// 编辑其他项目资料时不重复提交客户经理，只有明确调整才进入经理变更流程。
export function projectClientManagerPayload(form, baselineId, creating = false) {
  const managerId = String(form.clientManagerId || '').trim()
  if (!creating && managerId === String(baselineId || '').trim()) return {}
  return {
    clientManagerId: managerId || null,
    clientManagerChangeReason: String(form.clientManagerChangeReason || '').trim() || null,
  }
}

// 现客户经理只是详情中的姓名快照。旧表单即使把它混入请求，也不得触发旧版姓名/角色校验。
export function interpretationProjectWritePayload(data) {
  const { currentClientManager, current_client_manager, ...payload } = data
  return payload
}
