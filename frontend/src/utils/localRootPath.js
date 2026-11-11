const normalize=value=>String(value||'').trim().replaceAll('/','\\').replace(/\\+$/,'')
const absolute=path=>/^[a-z]:\\/i.test(path)||/^\\\\[^\\]+\\[^\\]+/.test(path)
const usable=path=>absolute(path)&&!path.includes('\0')&&!path.split('\\').some(part=>part==='.'||part==='..')&&!/^[a-z]:\\fakepath(?:\\|$)/i.test(path)

// “本地”不能把上一次 UNC 尝试当成浏览器返回的本地根目录。
// 当前输入仍可保留；文件/桌面选择器显式返回的绝对路径也不受此过滤影响。
export function localFolderCandidates(current,project={}){
  return [current,...[project.originalStoragePath,project.networkFilePath,project.sourceFolderPath].filter(value=>!normalize(value).startsWith('\\\\'))]
}

// 仅从浏览器/桌面明确提供的绝对路径或已有业务路径提取，绝不拼接猜测盘符。
export function givenLocalRootPath(rootName,{files=[],handle,candidates=[]}={}){
  if(!rootName)return ''
  const sources=[handle?.path,...Array.from(files).map(file=>file.path),...candidates]
  for(const source of sources){
    const path=normalize(source)
    if(!usable(path))continue
    const parts=path.split('\\')
    for(let index=parts.length-1;index>=0;index--){
      if(parts[index].toLocaleLowerCase()!==rootName.toLocaleLowerCase())continue
      const root=parts.slice(0,index+1).join('\\')
      if(usable(root))return root
    }
  }
  return ''
}
