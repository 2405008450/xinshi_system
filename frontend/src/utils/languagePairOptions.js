const indexes = new WeakMap()
const normalize = value => String(value || '').toLocaleLowerCase().replace(/\s+/g, '')
const directionQuery = value => normalize(value).replace(/翻译成为|翻译成|翻译为|转换成为|转换成|转换为|译成|译为|转成|转为|翻译|转换|->|=>|→|译|转|到|至/g, '')

// 只建立语种索引，按当前检索生成有限候选项，避免每个弹窗构造数十万条组合。
export function buildLanguagePairOptions(languages, commonPairs, query = '', {limit = 200, allowProofreading = false} = {}) {
  let entries = indexes.get(languages)
  if (!entries) {
    entries = languages.map(language => ({
      ...language,
      shortcuts: language.shortcuts?.length ? language.shortcuts : [language.label],
      search: normalize([language.label, language.code, language.nameEn, language.shortNameZh, language.shortNameEn, ...(language.aliases || [])].join('|')),
    }))
    indexes.set(languages, entries)
  }
  const tokens = String(query).toLocaleLowerCase().split(/[\s|/]+/).filter(Boolean).map(normalize)
  const directionTokens = tokens.map(directionQuery)
  const result = [], seen = new Set()
  const add = (source, target) => {
    if (result.length >= limit || source.id === target.id) return
    const value = `${source.label}→${target.label}`
    if (seen.has(value)) return
    const search = `${normalize(value)}|${source.search}|${target.search}`
    if (!tokens.every((token, index) => search.includes(token) || Boolean(directionTokens[index] && source.shortcuts.some(left => target.shortcuts.some(right => normalize(left + right).includes(directionTokens[index])))))) return
    seen.add(value)
    const shortest = values => [...values].sort((a, b) => a.length - b.length)[0] || ''
    result.push({label: value, value, isCustom: source.isCustom || target.isCustom,
      shortLabel: `${shortest(source.shortcuts)}译${shortest(target.shortcuts)}`})
  }
  if (allowProofreading) {
    for (const value of ['校对', '盖章']) {
      if (tokens.every(token => value.includes(token))) result.push({label: value, value, shortLabel: '业务标记'})
    }
  }
  const byCode = new Map(entries.map(item => [item.code, item]))
  for (const [sourceCode, targetCode] of commonPairs) {
    const source = byCode.get(sourceCode), target = byCode.get(targetCode)
    if (source && target) add(source, target)
  }
  for (const source of entries) {
    for (const target of entries) {
      add(source, target)
      if (result.length >= limit) return result
    }
  }
  return result
}
