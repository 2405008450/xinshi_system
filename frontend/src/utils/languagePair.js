const compactLanguageNames = new Map([
  ['中文（简体）', '简中'],
  ['中文(简体)', '简中'],
  ['中文（繁体）', '繁中'],
  ['中文(繁体)', '繁中'],
  ['英语（美国）', '美英'],
  ['英语(美国)', '美英'],
  ['美式英语', '美英'],
  ['英语（英国）', '英英'],
  ['英语(英国)', '英英'],
  ['英式英语', '英英'],
  ['葡萄牙语（巴西）', '巴西葡语'],
  ['葡萄牙语(巴西)', '巴西葡语'],
  ['葡萄牙语（葡萄牙）', '欧洲葡语'],
  ['葡萄牙语(葡萄牙)', '欧洲葡语'],
  ['西班牙语（拉美）', '拉美西语'],
  ['西班牙语(拉美)', '拉美西语'],
])

export const splitLanguagePairs = (value) => String(value || '')
  .split(/[；;,，\n]+/)
  .map((item) => item.trim())
  .filter(Boolean)

export const compactLanguageName = (value) => (
  compactLanguageNames.get(String(value || '').trim()) || String(value || '').trim()
)

export const compactLanguagePair = (value) => {
  const parts = String(value || '').split(/\s*(?:→|->|=>)\s*/)
  if (parts.length !== 2) return value || '-'
  return `${compactLanguageName(parts[0])}->${compactLanguageName(parts[1])}`
}

export const getLanguagePairSummary = (value) => {
  const pairs = splitLanguagePairs(value)
  return {
    primary: compactLanguagePair(pairs[0]),
    extraCount: Math.max(0, pairs.length - 1),
  }
}
