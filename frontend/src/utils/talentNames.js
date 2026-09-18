const normalizedName = (value) => String(value || '').trim()

export const getTalentDisplayName = (talent, fallback = '-') => {
  const names = [
    talent?.chineseName,
    talent?.englishName,
    talent?.nickname,
    ...(Array.isArray(talent?.otherNames) ? talent.otherNames : []),
    talent?.fullName,
  ]
  return names.map(normalizedName).find(Boolean) || fallback
}

export const countTalentNames = (talent) => [
  talent?.chineseName,
  talent?.englishName,
  talent?.nickname,
  ...(Array.isArray(talent?.otherNames) ? talent.otherNames : []),
].map(normalizedName).filter(Boolean).length
