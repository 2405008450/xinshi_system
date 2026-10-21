// 每个可信文档服务只加载一次 SDK；失败后移除脚本，允许重试。
const scripts = new Map()
export function loadOfficeScript(url) {
  if (scripts.has(url)) return scripts.get(url)
  const promise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    const timeout = window.setTimeout(() => finish(new Error('Office 编辑器加载超时')), 20000)
    function finish(error) {
      window.clearTimeout(timeout)
      script.onload = script.onerror = null
      if (error) { script.remove(); scripts.delete(url); reject(error) }
      else resolve(window.DocsAPI)
    }
    script.src = url
    script.async = true
    script.onload = () => finish(window.DocsAPI?.DocEditor ? null : new Error('Office 编辑器加载失败'))
    script.onerror = () => finish(new Error('无法连接 Office 文档服务'))
    document.head.appendChild(script)
  })
  scripts.set(url, promise)
  return promise
}
