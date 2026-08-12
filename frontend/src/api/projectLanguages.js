import api from './index'

const normalize = (item) => ({
  id: item.id,
  label: item.label,
  isCustom: item.is_custom ?? item.isCustom ?? false,
  createdBy: item.created_by ?? item.createdBy ?? null,
})

export const getProjectLanguages = () => (
  api.get('/projects/languages').then((rows) => (Array.isArray(rows) ? rows.map(normalize) : []))
)

export const createProjectLanguage = (label) => (
  api.post('/projects/languages', { label }).then(normalize)
)
