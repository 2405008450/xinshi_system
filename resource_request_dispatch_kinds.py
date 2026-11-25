"""资源需求的发送类别与平台发布类别。"""
POSTING_KINDS = frozenset({'post', 'wechat_public', 'xiaohongshu'})
DISPATCH_KINDS = POSTING_KINDS | {'circle'}
LABELS = {'circle':'发圈需求','post':'发帖需求','wechat_public':'公众号需求','xiaohongshu':'小红书需求','development':'资源需求管理'}
