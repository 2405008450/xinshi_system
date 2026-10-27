/** 发送参数与讨论接口一致；候选人员等显示状态只保存在本地草稿中。 */
export function discussionMessagePayload(source) {
  return {
    content: source.content,
    clientMessageId: source.clientMessageId,
    replyToId: source.replyToId ?? null,
    mentionedUserIds: [...(source.mentionedUserIds || [])],
    mentionAll: !!source.mentionAll,
  }
}
