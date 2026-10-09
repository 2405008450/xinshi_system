import { formatProjectNameDeadline, formatProjectNameLanguagePair } from './projectNaming.js'
import { extractSubjectPrefix } from './emailSubject.js'

export function buildTranslationEmailSubject(source = {}) {
  const deadline = formatProjectNameDeadline(source.customerDeadlineTime)
  const fields = [
    ['标题前缀', source.subjectPrefix],
    ['订单号', source.orderNo],
    ['客户简称', source.clientShortName],
    ['客户经理联系方式', source.managerContact],
    ['翻译方向', formatProjectNameLanguagePair(source.languagePair)],
    ['客户交稿时间', deadline ? `${deadline}回稿` : ''],
  ]
  const count = Math.max(0, Number(source.subOrderCount) || 0)
  if (count) fields.push(['批次', `${count}批`])
  const values = fields.map(([label, value]) => [label, String(value || '').trim()])
  const optional = new Set(['标题前缀', '客户经理联系方式', '批次'])
  const parts = values.map(([, value]) => value).filter(Boolean)
  return {
    parts,
    subject: parts.join('，'),
    missingFields: values.filter(([label, value]) => !optional.has(label) && !value).map(([label]) => label),
  }
}

export function extractTranslationSubjectPrefix(preview, form = {}) {
  const existing = String(form.subjectPrefix || '').trim()
  if (existing && existing.length <= 50) return existing
  const text = String(preview || '').trim()
  const { subject } = buildTranslationEmailSubject({ ...form, subjectPrefix: '' })
  if (subject && text === subject) return ''
  if (subject && text.endsWith(`，${subject}`)) {
    const prefix = text.slice(0, -(subject.length + 1)).trim()
    if (prefix.length <= 50) return prefix
  }
  // 用旧名称识别历史格式，不将历史业务摘要填回文件名。
  const legacyPrefix = extractSubjectPrefix(preview, form)
  if (legacyPrefix) return legacyPrefix
  // 名称改为文件名后，旧主题仍可通过前缀后紧接订单号的格式识别。
  const orderNo = String(form.orderNo || '').trim()
  const parts = text.split('，')
  return orderNo && parts[1]?.trim() === orderNo && parts[0].trim().length <= 50
    ? parts[0].trim() : ''
}
