// 地址只携带业务标识；登录凭证和文档服务配置均由新页面自行获取。
export function officePageUrl(request) {
  const query = new URLSearchParams({ project: request.projectId })
  if (request.file) query.set('file', request.file.file_id)
  else {
    query.set('create', request.create.kind)
    if (request.create.folderId) query.set('folder', request.create.folderId)
  }
  return `/annotation-office?${query}`
}

export function openOfficePage(request) {
  // 先在点击事件内同步打开，既能识别弹窗拦截，也避免异步获取资料后被浏览器阻止。
  const tab = window.open('about:blank', '_blank')
  if (!tab) return false
  tab.opener = null
  tab.location.replace(officePageUrl(request))
  return true
}
