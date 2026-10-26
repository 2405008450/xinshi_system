export const TASK_COPY_NOTICE = '自动复制自‘具体任务’，注意相应修改！！修改后删除本句话！！'
export const hasTaskCopyNotice = content => String(content || '').startsWith(`${TASK_COPY_NOTICE}\n`)
export const taskVersionBody = content => hasTaskCopyNotice(content) ? content.slice(TASK_COPY_NOTICE.length + 1) : (content || '')
const copiedContent = original => original.copiedFromTask && original.content && !hasTaskCopyNotice(original.content) ? `${TASK_COPY_NOTICE}\n${original.content}` : (original.content || '')
// 仅填充默认版本的空内容，或尚未被人工修改的上一次自动复制内容。
export function mergeTaskVersions(current = [], source = [], previousTask = '') {
  const versions = current.map(item => ({ ...item }))
  for (const original of source) {
    const name = String(original.name || '').replace(/版$/, '')
    if (!['发帖', '询问'].includes(name)) continue
    const index = versions.findIndex(item => String(item.name || '').replace(/版$/, '') === name)
    if (index < 0) { versions.push({ ...original, content: copiedContent(original) }); continue }
    const item = versions[index]
    if (!String(item.content || '').trim() || (item.copiedFromTask && (item.content === previousTask || (hasTaskCopyNotice(item.content) && taskVersionBody(item.content) === previousTask)))) {
      versions[index] = { ...item, content: copiedContent(original), copiedFromTask: Boolean(original.copiedFromTask) }
    }
  }
  return versions
}
