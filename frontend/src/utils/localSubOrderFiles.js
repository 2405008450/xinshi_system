import { translationFileNameError } from './translationFileName.js'

export function localSubOrderFiles(files, existingNames = []) {
  const existing = new Set(existingNames.map(name => String(name || '').trim().toLocaleLowerCase()))
  const seen = new Set()
  const entries = Array.from(files || []).filter(file => !file.webkitRelativePath || file.webkitRelativePath.split('/').length === 2)
    .filter(file => !['.ds_store', 'desktop.ini', 'thumbs.db'].includes(file.name.toLowerCase()) && !file.name.startsWith('~$'))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  if (entries.length > 500) throw new Error('单次最多选择 500 个文件，请分批处理')
  return entries.map((file, index) => {
    const name = file.name
    const key = name.trim().toLocaleLowerCase()
    let reason = translationFileNameError(name)
    let status = reason ? 'error' : 'create'
    if (!reason && (existing.has(key) || seen.has(key))) {
      status = 'duplicate'
      reason = existing.has(key) ? '当前母订单已存在同名子订单' : '本次选择中文件名称重复'
    }
    seen.add(key)
    return { id: index, lineNumber: index + 1, name, status, reason }
  })
}


export function localFolderEntries(files) {
  const entries=new Map()
  let total=0
  for(const file of Array.from(files||[])){
    const parts=String(file.webkitRelativePath||'').split('/')
    if(parts.length<2)continue
    if(['.ds_store','desktop.ini','thumbs.db'].includes(file.name.toLowerCase())||file.name.startsWith('~$'))continue
    if(parts.length>5)throw new Error('目录超过三层子文件夹，文件将超出四级子订单，请整理目录')
    const error=translationFileNameError(file.name)
    if(error)throw new Error(`${file.name}：${error}`)
    total++
    if(total>2000)throw new Error('单次最多读取2000个文件')
    for(let i=1;i<parts.length;i++){
      const key=parts.slice(0,i).join('/')
      if(!entries.has(key))entries.set(key,{relativePath:key,files:[]})
    }
    entries.get(parts.slice(0,-1).join('/')).files.push(file.name)
    if(entries.size>500)throw new Error('单次最多读取500个文件夹')
  }
  return [...entries.values()].sort((a,b)=>a.relativePath.localeCompare(b.relativePath,'zh-CN'))
}

export function folderOrderPreview(entries,rootPath='') {
  const result=[]
  const ordered=[...entries].sort((a,b)=>a.relativePath.localeCompare(b.relativePath,'zh-CN'))
  const pathFor=relative=>rootPath ? rootPath.replace(/[\\\/]$/,'')+(relative.includes('/')?'\\'+relative.split('/').slice(1).join('\\'):'') : relative
  for(const entry of ordered){
    const depth=entry.relativePath.split('/').length-1
    const empty=!entries.some(child=>(child.relativePath===entry.relativePath||child.relativePath.startsWith(entry.relativePath+'/'))&&child.files.length)
    result.push({name:entry.relativePath.split('/').at(-1),level:depth,empty,kind:empty?'空文件夹（不生成订单）':depth===0?'母订单':'文件夹',path:pathFor(entry.relativePath)})
    for(const name of entry.files)result.push({name,level:depth+1,kind:'文件',path:pathFor(entry.relativePath+'/'+name)})
  }
  return result
}


export async function enumerateFolderHandle(handle) {
  const entries=[];let total=0
  async function visit(directory,relative){
    if(relative.split('/').length>4)throw new Error('目录超过三层子文件夹，文件将超出四级子订单，请整理目录')
    const entry={relativePath:relative,files:[]};entries.push(entry)
    if(entries.length>500)throw new Error('单次最多读取500个文件夹')
    for await(const child of directory.values()){
      if(['.ds_store','desktop.ini','thumbs.db'].includes(child.name.toLowerCase())||child.name.startsWith('~$'))continue
      if(child.kind==='directory')await visit(child,relative+'/'+child.name)
      else if(child.kind==='file'){
        const error=translationFileNameError(child.name)
        if(error)throw new Error(`${child.name}：${error}`)
        entry.files.push(child.name);total++
        if(total>2000)throw new Error('单次最多读取2000个文件')
      }
    }
    entry.files.sort((a,b)=>a.localeCompare(b,'zh-CN'))
  }
  await visit(handle,handle.name)
  return entries
}
