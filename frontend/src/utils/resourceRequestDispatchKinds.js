export const postingDispatchKinds = ['post','wechat_public','xiaohongshu']
export const resourceDispatchLabels = {circle:'发圈需求',post:'发帖需求',wechat_public:'公众号需求',xiaohongshu:'小红书需求',development:'资源开拓 · 需求管理'}
export const emptyResourceDispatchRecords = () => Object.fromEntries(Object.keys(resourceDispatchLabels).map(kind=>[kind==='wechat_public'?'wechatPublic':kind,[]]))
