"""资源需求的发送类别与平台发布类别。"""
POSTING_KINDS = frozenset({'post', 'wechat_public', 'xiaohongshu'})
DISPATCH_KINDS = POSTING_KINDS | {'circle'}
PUBLIC_BROADCAST_KIND = 'wechat_broadcast'
LABELS = {'circle':'发圈需求','post':'发帖需求','wechat_public':'发圈（+公众号）需求','xiaohongshu':'小红书需求','development':'资源需求管理',PUBLIC_BROADCAST_KIND:'发圈（+公众号）需求 · 全体通知'}
