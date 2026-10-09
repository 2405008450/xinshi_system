import api from './index'
import { normalizeBlobApiError } from '@/utils/errorMessages'

const paths = {
  projects: 'export',
  reconciliation: 'reconciliation-export',
  client_reconciliation: 'reconciliation-export',
  translator_reconciliation: 'translator-reconciliation-export',
  personnel_reconciliation: 'personnel-reconciliation-export',
  candidate_tracking: 'candidate-tracking-export',
}

export async function exportProjectWorkbook(module, type, params, config = {}) {
  if (!['translation', 'interpretation', 'annotation', 'recruitment'].includes(module) || !paths[type]) {
    throw new Error('不支持的项目导出类型')
  }
  try {
    return await api.get(`/projects/${module}/${paths[type]}`, {
      ...config,
      params,
      responseType: 'blob',
      timeout: 120000,
    })
  } catch (error) {
    throw await normalizeBlobApiError(error)
  }
}
