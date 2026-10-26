// iPad 的桌面模式可能使用 Mac UA，不能把它标成电脑端。
export function chatClientType(navigatorInfo) {
  if (navigatorInfo.userAgentData?.mobile || /Android|iPhone|iPad|iPod|Mobile/i.test(navigatorInfo.userAgent || '') ||
      navigatorInfo.platform === 'MacIntel' && navigatorInfo.maxTouchPoints > 1) return 'mobile'
  return 'desktop'
}
