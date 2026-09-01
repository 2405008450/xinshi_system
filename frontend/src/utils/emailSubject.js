const EMAIL_SUBJECT_FIELDS = [
  ['标题前缀', 'subjectPrefix'],
  ['订单号', 'orderNo'],
  ['客户简称', 'clientShortName'],
  ['客户经理联系方式', 'managerContact'],
  ['客户单号/标识', 'customerOrderNo'],
  ['项目名称', 'projectName'],
]

export const COMMON_SUBJECT_PREFIX_OPTIONS = ['***急***']

export const buildEmailSubject = (source = {}) => {
  const values = EMAIL_SUBJECT_FIELDS.map(([label, key]) => [
    label,
    String(source[key] || '').trim(),
  ])
  return {
    subject: values.map(([, value]) => value).filter(Boolean).join('，'),
    missingFields: values
      .filter(([label, value]) => label !== '标题前缀' && !value)
      .map(([label]) => label),
  }
}

export const notifyEmailSubjectGenerated = (form, ElMessage) => {
  const { subject, missingFields } = buildEmailSubject(form)
  if (!subject) {
    ElMessage.warning('暂无可用于生成邮件主题的内容')
    return false
  }
  form.emailSubjectPreview = subject
  if (!String(form.orderNo || '').trim()) {
    ElMessage.warning('邮件主题已生成；新增项目尚无订单号，保存后请重新生成以补全订单号')
  } else if (missingFields.length) {
    ElMessage.warning(`邮件主题已生成，已跳过空字段：${missingFields.join('、')}`)
  } else {
    ElMessage.success('邮件主题已生成')
  }
  return true
}

export const extractSubjectPrefix = (preview, form = {}) => {
  const previewText = String(preview || '').trim()
  const existing = String(form.subjectPrefix || '').trim()
  if (existing && existing.length <= 50) return existing
  if (!previewText) return ''
  const generatedParts = [
    form.orderNo,
    form.clientShortName,
    form.managerContact,
    form.customerOrderNo,
    form.projectName,
  ].map((value) => String(value || '').trim()).filter(Boolean)
  if (!generatedParts.length) return ''

  const generatedSubject = generatedParts.join('，')
  if (previewText === generatedSubject) return ''

  // 仅当预览严格符合本页面的生成格式时才反推出标题前缀。
  // 历史数据或人工编辑的主题可能没有中文逗号，不能把整段预览误当作前缀。
  const suffix = `，${generatedSubject}`
  if (!previewText.endsWith(suffix)) return ''

  const prefix = previewText.slice(0, -suffix.length).trim()
  return prefix.length <= 50 ? prefix : ''
}
