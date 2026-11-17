export const countPathKey = path => String(path || '').replaceAll('\\', '/').replace(/\/+$/, '').toLowerCase()

export function orderFileTargets(rows, rootPath) {
  const root = countPathKey(rootPath)
  if (!root) return []
  const candidates = []
  const pathCounts = new Map()
  for (const row of rows) {
    if (row.folderInfo || row.wordCountCopyBaseline || row.wordCountMatrixSource === 'suborder_aggregate') continue
    const fullPath = row.networkFilePath
    const key = countPathKey(fullPath)
    if (!key.startsWith(root + '/')) continue
    const path = fullPath.replaceAll('\\', '/').slice(root.length + 1)
    pathCounts.set(key, (pathCounts.get(key) || 0) + 1)
    candidates.push({ id: row.id, orderNo: row.subOrderNo, fullPath, path, key })
  }
  return candidates.filter(item => pathCounts.get(item.key) === 1)
}

export function* countFileBatches(files) {
  let batch = []
  let bytes = 0
  for (const file of files) {
    if (batch.length === 50 || bytes + file.size > 200 * 1024 ** 2) {
      yield batch
      batch = []
      bytes = 0
    }
    batch.push(file)
    bytes += file.size
  }
  if (batch.length) yield batch
}
