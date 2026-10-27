export const regionFields = [
  { key: 'ancestral_home', label: '籍贯' },
  { key: 'native_place', label: '主要成长地' },
  { key: 'residence_address', label: '目前所在地' },
]
export const regionSuffixes = ['省', '市', '区', '县', '镇', '乡', '自治州', '自治县', '自治区']

export function prepareRegionSource(value, rules = {}) {
  const source = String(value || '').normalize('NFKC').trim()
  if (rules.matchMode !== 'trim_suffix' || (rules.preserveShort !== false && Array.from(source).length <= 2)) return source
  const suffix = [...(rules.suffixes || [])].sort((a, b) => b.length - a.length).find(item => source.endsWith(item))
  return suffix ? source.slice(0, -suffix.length).trim() : source
}

// 以字符位置删除，重复字可单独选择；不修改文件原文。
export function removeRegionCharacters(value, positions = []) {
  const removed = new Set(positions)
  return Array.from(String(value || '')).filter((_, index) => !removed.has(index)).join('')
}
export function columnLetter(index) {
  let result = ''
  for (; index >= 0; index = Math.floor(index / 26) - 1) result = String.fromCharCode(65 + index % 26) + result
  return result
}
// Excel 复制区域为 TSV；保留被引号包裹的制表符、换行和双引号。
export function parsePastedRegions(text, header = false) {
  const matrix = [], row = []
  let value = '', quoted = false
  const input = String(text || '').replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
  for (let i = 0; i < input.length; i++) {
    const char = input[i]
    if (char === '"' && (quoted || !value)) {
      if (quoted && input[i + 1] === '"') { value += '"'; i++ }
      else quoted = !quoted
    } else if (!quoted && (char === '\t' || char === '\n')) {
      row.push(value); value = ''
      if (char === '\n') { matrix.push(row.splice(0)); if (matrix.length > 1002) throw new Error('一次最多匹配1000行') }
    } else value += char
  }
  if (quoted) throw new Error('粘贴内容中存在未闭合的引号，请重新复制完整区域')
  row.push(value); matrix.push(row)
  const data = matrix.map((values, index) => ({ values, source_row: index + 1 })).filter(item => item.values.some(cell => cell.trim()))
  const headings = header && data.length ? data.shift().values : []
  if (!data.length) throw new Error('请粘贴至少一行区域数据')
  if (data.length > 1000) throw new Error('一次最多匹配1000行')
  const width = Math.max(headings.length, ...data.map(item => item.values.length))
  if (width > 50) throw new Error('最多支持50列，请仅复制需要匹配的区域')
  if (data.some(item => item.values.some(cell => cell.length > 1000))) throw new Error('单元格内容过长，请只粘贴区域数据')
  for (const item of data) item.values = Array.from({ length: width }, (_, index) => item.values[index] || '')
  return { columns: Array.from({ length: width }, (_, index) => ({ index, label: `${columnLetter(index)}列 · ${headings[index]?.trim() || columnLetter(index)}` })), rows: data }
}
export function buildRegionPayload(data, sourceColumns, mapping, threshold, combine, targetCombine, rules = {}, overrides = {}) {
  if (!data.rows.length) throw new Error('请先上传表格或读取粘贴区域')
  if (!sourceColumns.length || sourceColumns.length > 3) throw new Error('请选择1～3个来源列')
  const mappings = sourceColumns.map(index => ({ source_column: index, target_fields: mapping[index] || [] }))
  if (mappings.some(item => !item.target_fields.length)) throw new Error('请为每个来源列选择目标字段')
  if (data.rows.some(row => sourceColumns.some(index => (row.values[index] || '').length > 255))) throw new Error('用于匹配的单元格最多255个字符')
  if (!Number.isInteger(threshold) || threshold < 50 || threshold > 100 || threshold % 10) throw new Error('匹配精度请选择50%、60%、70%、80%、90%或100%')
  return {
    rows: data.rows.map((item, rowIndex) => item.values.map((value, columnIndex) => overrides[rowIndex]?.[columnIndex] ?? value)),
    mappings, threshold: 100, combine, target_combine: targetCombine,
    match_mode: rules.matchMode || 'full', suffixes: [...(rules.suffixes || [])], preserve_short: rules.preserveShort !== false,
  }
}
