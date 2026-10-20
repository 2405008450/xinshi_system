// 空白分词、词间 AND、大小写不敏感；输入作为普通文本，不解析正则或 SQL 通配符。
export const searchTerms = value => [...new Set(String(value ?? '').toLowerCase().trim().split(/\s+/u).filter(Boolean))]
export const matchesSearch = (value, keyword) => {
  const haystack = String(value ?? '').toLowerCase()
  return searchTerms(keyword).every(term => haystack.includes(term))
}
export const matchesSearchFields = (values, keyword) => matchesSearch(values.map(value => String(value ?? '')).join(' '), keyword)
