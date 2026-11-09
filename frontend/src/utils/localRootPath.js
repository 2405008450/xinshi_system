const normalize=value=>String(value||'').trim().replaceAll('/','\\').replace(/\\+$/,'')
const absolute=path=>/^[a-z]:\\/i.test(path)||/^\\\\[^\\]+\\[^\\]+/.test(path)
const usable=path=>absolute(path)&&!path.includes('\0')&&!path.split('\\').some(part=>part==='.'||part==='..')&&!/^[a-z]:\\fakepath(?:\\|$)/i.test(path)

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
