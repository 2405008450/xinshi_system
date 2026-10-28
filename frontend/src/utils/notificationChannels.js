// 与后端 notification_channels.py 保持一致；未知业务类型继续进入通知。
export const CHAT_NOTIFICATION_TYPES = [
  'discussion_chat', 'annotation_project_chat', 'discussion_chat_mention', 'project_chat', 'project_chat_mention', 'annotation_project_chat_mention',
  'annotation_project_chat_invite', 'direct_chat', 'direct_chat_mention', 'direct_chat_invite',
]
export const isChatNotification = item => CHAT_NOTIFICATION_TYPES.includes(String(item?.notification_type || ''))
export const isBusinessNotification = item => !isChatNotification(item)
export const isChatMentionNotification = item => isChatNotification(item) && String(item.notification_type).endsWith('_mention')
// 普通消息、提及与邀请均主动提醒；持续时间由调用方决定。
export const isChatAttentionNotification = isChatNotification
