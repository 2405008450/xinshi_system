import categories from '../config/translationFileExtensions.json' with { type: 'json' }
export const translationFileExtensionCategories = categories
const extensions = new Set(Object.values(categories).flat())
const known = value => extensions.has(value.toLowerCase()) || /^(?:[rz]\d{2}|\d{3})$/i.test(value)
export function translationFileNameError(value, {allowMissingExtension=false}={}) {
  const name = String(value || '').replace(/^\uFEFF/, '').trim()
  if(!name) return '请输入项目名称（真实文件名）'
  if([...name].length > 255) return '项目名称不能超过255个字符'
  const multiple = '一个订单号只能对应一个文件名，请将多个文件拆分为独立订单'
  const tokens = [...name.matchAll(/\.([a-zA-Z0-9][a-zA-Z0-9_-]{0,19})(?=$|[\s,，;；、|+&])/g)].filter(match=>known(match[1]))
  if(tokens.length > 1) return multiple
  if(/[<>:"/\\?*\x00-\x1f]/.test(name) || name.endsWith('.')) return '请输入单个真实文件名，不要填写路径、引号或文件名禁用字符'
  if(allowMissingExtension && !tokens.length) return ''
  if(!name.includes('.')) return '文件名称必须保留完整扩展名（如 .docx、.pdf、.mp4、.jpg、.zip）；未知格式请先核对后缀；如有子订单，母订单项目名称可不带扩展名'
  if(!/[^.\s]/.test(name.slice(0,name.lastIndexOf('.')))) return '扩展名前必须有文件名称，不能只填写 .pdf 等后缀'
  if(!tokens.length || tokens.at(-1).index + tokens.at(-1)[0].length !== name.length) return '文件名称必须保留完整扩展名（如 .docx、.pdf、.mp4、.jpg、.zip）；未知格式请先核对后缀；如有子订单，母订单项目名称可不带扩展名'
  return ''
}
export function validateTranslationFileName(_rule, value, callback) {
  const message = translationFileNameError(value)
  callback(message ? new Error(message) : undefined)
}

export function translationFileExtension(value) {
  const name=String(value||'').trim().toLowerCase()
  const longest=[...extensions].sort((a,b)=>b.length-a.length).find(ext=>name.endsWith('.'+ext))
  if(longest) return '.'+longest
  const last=name.split('.').at(-1)
  return name.includes('.') && known(last) ? '.'+last : ''
}
