const EMAIL_SUBJECT_FIELDS = [
  ['标题前缀', 'subjectPrefix'],
  ['订单号', 'orderNo'],
  ['客户简称', 'clientShortName'],
  ['负责人联系方式', 'managerContact'],
  ['客户单号/标识', 'customerOrderNo'],
  ['项目名称', 'projectName'],
]

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
  if (existing) return existing
  if (!previewText) return ''
  const known = [
    form.orderNo,
    form.clientShortName,
    form.managerContact,
    form.customerOrderNo,
    form.projectName,
  ].map((value) => String(value || '').trim()).filter(Boolean)
  const parts = previewText.split('，').map((item) => item.trim()).filter(Boolean)
  if (!parts.length) return ''
  const orderNo = String(form.orderNo || '').trim()
  if (orderNo && parts[0] === orderNo) return ''
  if (orderNo && parts.length >= 2 && parts[1] === orderNo) return parts[0]
  if (known.includes(parts[0])) return ''
  return parts[0]
}

