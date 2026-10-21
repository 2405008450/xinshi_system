// 仅在云端 Word／Excel 编辑器入口注入；通过父页面握手转发保存意图，不传输正文或凭证。
(() => {
  if (window.parent === window) return
  let parentOrigin
  try {
    const referrer = new URL(document.referrer)
    if (!/^https?:$/.test(referrer.protocol)) return
    parentOrigin = referrer.origin
  } catch { return }
  const channel = 'xinshi-office-save-v1'
  let nonce = null
  window.addEventListener('message', event => {
    if (event.source !== window.parent || event.origin !== parentOrigin || event.data?.channel !== channel) return
    if (event.data.type !== 'connect' || typeof event.data.nonce !== 'string' || !/^[a-f0-9-]{36}$/.test(event.data.nonce)) return
    nonce = event.data.nonce
    window.parent.postMessage({ channel, type: 'connected', nonce }, parentOrigin)
  })
  window.addEventListener('keydown', event => {
    if (!nonce || event.isComposing || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== 's') return
    event.preventDefault()
    // 继续让编辑器处理原生保存，以便提交正在输入的 Excel 单元格并同步到文档服务。
    if (!event.repeat) window.parent.postMessage({ channel, type: 'save', nonce }, parentOrigin)
  }, true)
  window.parent.postMessage({ channel, type: 'ready' }, parentOrigin)
})()
