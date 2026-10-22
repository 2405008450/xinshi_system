// 只决定通用聊天入口的默认分组；项目行的沟通入口仍打开指定订单。
export function chatEntryContext(route) {
  if (route.meta?.chatContext) return route.meta.chatContext
  const section = String(route.path || '').split('/')[1]
  for (const kind of ['annotation', 'translation', 'interpretation', 'recruitment']) {
    if (section === kind || section.startsWith(`${kind}-`)) return kind
  }
  return ''
}
