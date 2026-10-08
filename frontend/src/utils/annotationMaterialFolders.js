// 目录只作为业务关联，不用于拼接物理存储路径。
export function folderNameError(name, folders, parentId = null) {
  const value = name.trim()
  if (!value || [...value].length > 100 || value === '.' || value === '..') return '文件夹名称不能为空、超过100字符或使用点号路径'
  if (/[\/\\\p{Cc}]/u.test(value)) return '文件夹名称不能包含路径分隔符或控制字符'
  if (folders.some(folder => (folder.parent_id || null) === parentId && folder.name === value)) return '同一目录下已存在同名文件夹'
  return ''
}

export function buildFolderTree(folders) {
  return [{ key: '@root', id: null, name: '项目资料（根目录）', children: folders.filter(folder => !folder.parent_id).map(folder => ({
    ...folder, key: folder.id, children: folders.filter(child => child.parent_id === folder.id).map(child => ({ ...child, key: child.id })),
  })) }]
}

export function folderParentId(folders, selectedId) {
  const folder = folders.find(item => item.id === selectedId)
  return folder ? (folder.parent_id || folder.id) : null
}

export function folderPath(folders, selectedId) {
  const folder = folders.find(item => item.id === selectedId)
  if (!folder) return '项目资料（根目录）'
  const parent = folders.find(item => item.id === folder.parent_id)
  return ['项目资料', parent?.name, folder.name].filter(Boolean).join(' / ')
}

export function newFolderId() {
  // 局域网 HTTP 也支持 getRandomValues，不依赖安全上下文中的 randomUUID。
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
