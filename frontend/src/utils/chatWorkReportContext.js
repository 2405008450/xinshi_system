const types = { AP: 'annotation', TP: 'translation', IP: 'interpretation', RP: 'recruitment' }

// 使用当前会话已显示的资料填写本人的报告，不额外请求项目详情或扩大访问权限。
// 讨论室编号不是项目编号，没有真实项目 ID 时只填写订单号与项目名称。
export function displayedReportProject({ projectId, projectType, title = '', orderNo = '' }) {
  const order = `${orderNo} ${title}`.match(/\b(AP|TP|IP|RP)-\d{6}-\d+(?:\.\d{3}){0,2}\b/)?.[0] || ''
  const native = ['annotation', 'translation'].includes(projectType)
  const type = native ? projectType : types[order.split('-')[0]]
  if (!type) return null
  return { id: native ? projectId : null, type, name: title || order, orderNo: order }
}
