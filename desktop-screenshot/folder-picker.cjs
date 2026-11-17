const fs=require('node:fs/promises'),path=require('node:path')
const {randomUUID}=require('node:crypto')
const maxCountFileBytes=50*1024*1024
const countableFile=/\.(docx?|xlsx?|pptx?|pdf|txt)$/i
const ignoredFile=name=>['.ds_store','desktop.ini','thumbs.db'].includes(name.toLowerCase())||name.startsWith('~$')
const singleSourceMessage='本选项卡只提取一级文件夹里的一个文件。目录有多个文件或包含子文件夹时，请到「新增母子订单」选项卡处理。'
async function singleLocalSource(root){
 const resolved=await fs.realpath(root)
 if(!/^[a-z]:\\/i.test(resolved))throw Error('请选择本地盘符路径，网络共享请填写 UNC 路径')
 const info=await fs.lstat(root)
 if(info.isSymbolicLink())throw Error('原文路径不能使用符号链接或目录联接')
 if(info.isFile())return resolved
 if(!info.isDirectory())throw Error('原文路径中没有可读取的文件')
 let file
 const directory=await fs.opendir(resolved)
 for await(const entry of directory){
  if(entry.isDirectory()||entry.isSymbolicLink())throw Error(singleSourceMessage)
  if(!entry.isFile()||ignoredFile(entry.name))continue
  if(file)throw Error(singleSourceMessage)
  file=path.join(resolved,entry.name)
 }
 if(!file)throw Error('原文路径中没有可读取的文件')
 return file
}
async function readSelectedFile(file, info){
 if(!info.isFile()||info.isSymbolicLink())throw Error('文件已变化或无法读取')
 if(info.size>maxCountFileBytes)throw Error('单文件超过 50 MB')
 const handle=await fs.open(file,'r')
 try{
  const current=await handle.stat()
  if(!current.isFile()||current.dev!==info.dev||current.ino!==info.ino||current.size>maxCountFileBytes)throw Error('文件已变化或超过 50 MB')
  const buffer=Buffer.alloc(current.size)
  const {bytesRead}=await handle.read(buffer,0,current.size,0)
  return buffer.subarray(0,bytesRead)
 }finally{await handle.close()}
}
async function enumerate(root, onFile){
 const entries=[];let files=0
 async function visit(directory,relative){
  if(relative.split('/').length>4)throw Error('目录超过三层子文件夹，请整理后再导入')
  const entry={relativePath:relative,files:[]};entries.push(entry)
  if(entries.length>500)throw Error('单次最多读取500个文件夹')
  const children=await fs.readdir(directory,{withFileTypes:true})
  for(const child of children){
   if(ignoredFile(child.name))continue
   if(child.isSymbolicLink())throw Error(`文件夹包含链接或目录联接，请改用实际目录：${relative}/${child.name}`)
   if(child.isDirectory())await visit(path.join(directory,child.name),relative+'/'+child.name)
   else if(child.isFile()){
    entry.files.push(child.name)
    if(++files>2000)throw Error('单次最多读取2000个文件')
    if(onFile)onFile(relative+'/'+child.name,path.join(directory,child.name))
   }
  }
  entry.files.sort((a,b)=>a.localeCompare(b,'zh-CN'))
 }
 await visit(root,path.basename(root));return entries
}
function registerFolderPicker({ipcMain,dialog},getWindow,trusted){
 let picking=false
 let selectedFolder
 function trustedWindow(event){
  const win=getWindow()
  if(!win||event.sender!==win.webContents||event.senderFrame!==win.webContents.mainFrame||!trusted(event.senderFrame.url))throw Error('请在系统桌面窗口中选择文件夹')
  return win
 }
 ipcMain.handle('xinshi:choose-translation-folder',async (event, kind)=>{
  const win=trustedWindow(event)
  if(!win.isFocused())throw Error('请在系统桌面窗口中选择文件夹')
  if(picking)throw Error('正在选择文件夹，请稍候')
  picking=true
  try{
   const isUnc = kind === 'unc'
   const result=await dialog.showOpenDialog(win,{title:isUnc?'选择笔译项目 UNC 根文件夹':'选择笔译项目根文件夹',properties:['openDirectory']})
   if(result.canceled||!result.filePaths?.length)return null
   if (isUnc) {
    const rootPath = path.win32.normalize(result.filePaths[0])
    if (!/^\\\\[^\\]+\\[^\\]+/.test(rootPath)) throw Error('请选择 UNC 共享文件夹，或直接填写完整 UNC 路径')
    return { rootPath }
   }
   const rootPath=path.resolve(result.filePaths[0])
   if(!path.basename(rootPath))throw Error('请选择具体根文件夹，不要只选择盘符')
   if(kind!=='local-count')return {rootPath,entries:await enumerate(rootPath)}
   const files=new Map()
   const entries=await enumerate(rootPath,(relative,file)=>{
    if(countableFile.test(file))files.set(relative,file)
   })
   const id=randomUUID()
   selectedFolder={id,root:await fs.realpath(rootPath),files,sender:event.sender}
   return {rootPath,entries,folderId:id}
  }finally{picking=false}
 })
 ipcMain.handle('xinshi:translation-folder-file', async (event,id,relative,read)=>{
  trustedWindow(event)
  const selection=selectedFolder
  const file=selection?.files.get(relative)
  if(!file||selection.id!==id||selection.sender!==event.sender)throw Error('文件不属于当前选择的文件夹')
  const real=await fs.realpath(file)
  const inside=path.relative(selection.root,real)
  if(!inside||path.isAbsolute(inside)||inside==='..'||inside.startsWith('..'+path.sep))throw Error('文件超出所选目录')
  const info=await fs.lstat(file)
  if(!info.isFile()||info.isSymbolicLink())throw Error('文件已变化或无法读取')
  if(!read)return info.size
  return readSelectedFile(real,info)
 })
 ipcMain.handle('xinshi:single-translation-source',async(event,value)=>{
  const win=trustedWindow(event)
  if(!win.isFocused())throw Error('请在系统桌面窗口中操作')
  if(typeof value!=='string'||value.length>2048||!/^[a-z]:[\\/]/i.test(value)
    ||/[\x00-\x1f:*?"<>|]/.test(value.slice(2))||value.split(/[\\/]/).some(part=>part==='.'||part==='..')){
   throw Error('请输入本地文件或文件夹的完整路径')
  }
  const confirmed=await dialog.showMessageBox(win,{
   type:'question',message:'读取这个本地原文路径？',detail:value,
   buttons:['读取','取消'],defaultId:0,cancelId:1,noLink:true,
  })
  if(confirmed.response!==0)return null
  const file=await singleLocalSource(value)
  const name=path.basename(file)
  if(!countableFile.test(name))return {name,message:'该格式暂不支持自动统计'}
  try{
   return {name,bytes:await readSelectedFile(file,await fs.lstat(file))}
  }catch(error){
   return {name,message:error.message}
  }
 })
}
module.exports={enumerate,registerFolderPicker}
