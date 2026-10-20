// 项目资料在线编辑：格式识别、文本编解码和文件名校验；不依赖浏览器 DOM，便于 node 测试。
export const ONLINE_EDIT_KINDS = {
  docx: { extension: '.docx', label: 'Word 文档', limit: 20 * 1024 * 1024 },
  markdown: { extension: '.md', label: 'Markdown', limit: 5 * 1024 * 1024 },
  text: { extension: '.txt', label: '文本文件', limit: 5 * 1024 * 1024 },
}
export const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export function onlineEditKind(name) {
  const value = String(name || '').toLowerCase()
  if (value.endsWith('.docx')) return 'docx'
  if (value.endsWith('.md')) return 'markdown'
  if (value.endsWith('.txt')) return 'text'
  return null
}

export function onlineEditBlocker(row) {
  const kind = onlineEditKind(row?.original_name)
  if (!kind) return '仅支持在线编辑 docx、md、txt 文件'
  if (row.file_size > ONLINE_EDIT_KINDS[kind].limit) return `文件超过 ${ONLINE_EDIT_KINDS[kind].limit / 1024 / 1024}MB，请下载后在本地编辑`
  return ''
}

// 用户输入的新文档名：自动补扩展名，规则与目录名一致，避免路径分隔符和控制字符。
export function documentFileName(name, kind) {
  const value = String(name || '').trim()
  const { extension } = ONLINE_EDIT_KINDS[kind]
  return onlineEditKind(value) === kind ? value : `${value}${extension}`
}

export function documentNameError(name, kind, siblingNames = []) {
  const value = String(name || '').trim()
  if (!value || value === '.' || value === '..') return '文件名不能为空或使用点号路径'
  if (/[\/\\\p{Cc}]/u.test(value)) return '文件名不能包含路径分隔符或控制字符'
  const fileName = documentFileName(value, kind)
  if ([...fileName].length > 255) return '文件名不能超过255个字符'
  if (siblingNames.some(item => item.toLowerCase() === fileName.toLowerCase())) return '当前目录下已存在同名文件'
  return ''
}

// 识别 BOM 与换行符；非 UTF-8 文本回退 GB18030（兼容 GBK），保存时统一写 UTF-8。
export function decodeText(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer)
  let text, encoding, bom = false
  if (bytes[0] === 0xEF && bytes[1] === 0xBB && bytes[2] === 0xBF) {
    text = new TextDecoder('utf-8').decode(bytes.subarray(3)); encoding = 'utf-8'; bom = true
  } else if (bytes[0] === 0xFF && bytes[1] === 0xFE) {
    text = new TextDecoder('utf-16le').decode(bytes.subarray(2)); encoding = 'utf-16le'
  } else if (bytes[0] === 0xFE && bytes[1] === 0xFF) {
    text = new TextDecoder('utf-16be').decode(bytes.subarray(2)); encoding = 'utf-16be'
  } else {
    try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); encoding = 'utf-8' }
    catch { text = new TextDecoder('gb18030').decode(bytes); encoding = 'gb18030' }
  }
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  return { text: text.replace(/\r\n/g, '\n'), encoding, bom, eol }
}

export function encodeText(text, { eol = '\n', bom = false } = {}) {
  const body = new TextEncoder().encode(String(text).replace(/\r\n/g, '\n').replace(/\n/g, eol))
  if (!bom) return body
  const result = new Uint8Array(body.length + 3)
  result.set([0xEF, 0xBB, 0xBF]); result.set(body, 3)
  return result
}

export function textMime(kind) {
  return kind === 'markdown' ? 'text/markdown;charset=utf-8' : 'text/plain;charset=utf-8'
}
