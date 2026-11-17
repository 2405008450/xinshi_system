import api from './index'

export const documentCountMetrics = [
  { key: 'words', label: '字数', width: 90 },
  { key: 'characters_no_spaces', label: '字符数（不计空格）', width: 145 },
  { key: 'cjk_chars_korean_words', label: '中朝统计', width: 100 },
]

export function documentCountValues(result) {
  if (result?.status !== 'counted') return {}
  return Object.fromEntries(documentCountMetrics
    .map(({ key }) => [key, result[key]])
    .filter(([, value]) => Number.isSafeInteger(value) && value >= 0))
}

export function uploadDocumentCount(files, signal) {
  const form = new FormData()
  files.forEach(file => form.append('files', file))
  return api.post('/document-word-count/upload', form, {
    signal, timeout: 120000, headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function waitForDocumentCount(id, signal, onProgress) {
  while (!signal.aborted) {
    const job = await api.get('/document-word-count/jobs/' + id, { signal })
    onProgress?.(job)
    if (job.status === 'completed' || job.status === 'failed') return job.files || []
    await new Promise(resolve => setTimeout(resolve, 800))
  }
  return []
}

export const inspectSingleSharedSource = (path, signal) =>
  api.post('/document-word-count/single-path', { path }, { signal, timeout: 60000 })
