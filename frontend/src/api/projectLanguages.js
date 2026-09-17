import api from './index'
import { getCachedOptions, invalidateOptionCache } from '@/utils/optionCache'

const ACTIVE_LANGUAGE_CACHE_KEY = 'project-languages:active'

const normalize = (item) => ({
  id: item.id,
  label: item.label,
  isCustom: item.is_custom ?? item.isCustom ?? false,
  createdBy: item.created_by ?? item.createdBy ?? null,
  code: item.code || '',
  nameZh: item.name_zh ?? item.nameZh ?? item.label,
  nameEn: item.name_en ?? item.nameEn ?? '',
  shortNameZh: item.short_name_zh ?? item.shortNameZh ?? '',
  shortNameEn: item.short_name_en ?? item.shortNameEn ?? '',
  languageType: item.language_type ?? item.languageType ?? 'language',
  aliases: Array.isArray(item.aliases) ? item.aliases : [],
  shortcuts: Array.isArray(item.shortcuts) ? item.shortcuts : [],
  matchedAlias: item.matched_alias ?? item.matchedAlias ?? '',
  matchType: item.match_type ?? item.matchType ?? '',
})

export const getProjectLanguages = () => getCachedOptions(
  ACTIVE_LANGUAGE_CACHE_KEY,
  () => api.get('/projects/languages').then((rows) => (Array.isArray(rows) ? rows.map(normalize) : [])),
  { ttlMs: 5 * 60_000 },
)

export const createProjectLanguage = (label) => (
  api.post('/projects/languages', { label }).then((item) => {
    invalidateOptionCache(ACTIVE_LANGUAGE_CACHE_KEY)
    return normalize(item)
  })
)

export const searchProjectLanguages = (keyword, limit = 50) => api.get('/projects/languages', {
  params: { keyword, limit },
}).then((rows) => (Array.isArray(rows) ? rows.map(normalize) : []))
