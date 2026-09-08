import api from './index'
import { getCachedOptions, invalidateOptionCache } from '@/utils/optionCache'

const ACTIVE_LANGUAGE_CACHE_KEY = 'project-languages:active'

const normalize = (item) => ({
  id: item.id,
  label: item.label,
  isCustom: item.is_custom ?? item.isCustom ?? false,
  createdBy: item.created_by ?? item.createdBy ?? null,
  code: item.code || '',
  aliases: Array.isArray(item.aliases) ? item.aliases : [],
  shortcuts: Array.isArray(item.shortcuts) ? item.shortcuts : [],
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
