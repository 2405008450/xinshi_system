const encodePathSegment = (segment) => encodeURIComponent(segment)

const normalizeUncPath = (path) => {
  const value = String(path || '').trim().replace(/\//g, '\\')
  if (!value.startsWith('\\\\') || value.includes('\0')) return ''

  const segments = value.slice(2).split('\\').filter(Boolean)
  if (segments.length < 2 || segments.some((segment) => segment === '.' || segment === '..')) return ''
  return `\\\\${segments.join('\\')}`
}

const allowedRoots = String(import.meta.env.VITE_OPENPATH_ALLOWED_ROOTS || '')
  .split(';')
  .map(normalizeUncPath)
  .filter(Boolean)

const isWithinAllowedRoot = (path) => {
  const candidate = path.toLocaleLowerCase('en-US')
  return allowedRoots.some((root) => {
    const normalizedRoot = root.replace(/\\+$/, '').toLocaleLowerCase('en-US')
    return candidate === normalizedRoot || candidate.startsWith(`${normalizedRoot}\\`)
  })
}

/**
 * 将 UNC 网络路径转换为 openpath 自定义协议地址。
 * 路径分隔符必须使用正斜杠，否则浏览器会把地址判定为无效 URL。
 */
export const toOpenPathHref = (path) => {
  const value = normalizeUncPath(path)
  if (!value || !isWithinAllowedRoot(value)) return ''

  const normalized = value.replace(/\\/g, '/').replace(/^\/+/, '')
  const [server = '', ...pathSegments] = normalized.split('/')
  if (!server) return ''

  const encodedPath = pathSegments.map(encodePathSegment).join('/')
  // 即使只打开服务器根路径也保留结尾的 /，保证它是完整的层级 URL。
  return `openpath://${encodePathSegment(server)}/${encodedPath}`
}

/**
 * 通过临时链接唤起系统自定义协议，避免给 Location.href 赋值时
 * 浏览器直接抛出 DOMException 并中断当前页面逻辑。
 */
export const launchOpenPath = (path) => {
  const href = toOpenPathHref(path)
  if (!href) return false

  const link = document.createElement('a')
  link.href = href
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  return true
}
