// 与后端 notification_channels.py 保持一致；未知业务类型继续进入通知。
export const CHAT_NOTIFICATION_TYPES = [
  'discussion_chat_mention', 'project_chat', 'project_chat_mention', 'annotation_project_chat_mention',
  'annotation_project_chat_invite', 'direct_chat', 'direct_chat_mention', 'direct_chat_invite',
]
export const isChatNotification = item => CHAT_NOTIFICATION_TYPES.includes(String(item?.notification_type || ''))
export const isBusinessNotification = item => !isChatNotification(item)
export const isChatMentionNotification = item => isChatNotification(item) && String(item.notification_type).endsWith('_mention')
// 普通留言只在会话列表显示弱提示；提及和邀请仍可主动提醒。
export const isChatAttentionNotification = item => isChatMentionNotification(item) || (
  isChatNotification(item) && String(item.notification_type).endsWith('_invite')
)
