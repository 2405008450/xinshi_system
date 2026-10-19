// 归属切换保留输入原文、换行和节点时间；合并只追加，绝不截断。
export function combineAnnotationProgressDrafts(existing, incoming) {
  if (existing.editingId || incoming.editingId) throw new Error('请先保存或取消客户进度编辑，再切换进度归属')
  const previous = String(existing.changeNote || '')
  const current = String(incoming.changeNote || '')
  const changeNote = previous && current ? `${previous}\n\n${current}` : previous || current
  if (changeNote.length > 10000) throw new Error('合并后的具体进度超过 10000 字，请先整理内容；两边草稿均已保留')
  const sources = [existing.source, incoming.source].filter(Boolean)
  const source = sources.length ? {
    messageCount: sources.reduce((total, item) => total + item.messageCount, 0),
    senderSummary: [...new Set(sources.flatMap((item) => String(item.senderSummary || '').split('、')).filter(Boolean))].join('、'),
  } : null
  return { changeNote, effectiveOn: incoming.effectiveOn, source }
}
