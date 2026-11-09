const fs=require('node:fs/promises'),path=require('node:path')
async function enumerate(root){
 const entries=[];let files=0
 async function visit(directory,relative){
  if(relative.split('/').length>4)throw Error('目录超过三层子文件夹，请整理后再导入')
  const entry={relativePath:relative,files:[]};entries.push(entry)
  if(entries.length>500)throw Error('单次最多读取500个文件夹')
  const children=await fs.readdir(directory,{withFileTypes:true})
  for(const child of children){
   if(['.ds_store','desktop.ini','thumbs.db'].includes(child.name.toLowerCase())||child.name.startsWith('~$'))continue
   if(child.isSymbolicLink())throw Error(`文件夹包含链接或目录联接，请改用实际目录：${relative}/${child.name}`)
   if(child.isDirectory())await visit(path.join(directory,child.name),relative+'/'+child.name)
   else if(child.isFile()){entry.files.push(child.name);if(++files>2000)throw Error('单次最多读取2000个文件')}
  }
  entry.files.sort((a,b)=>a.localeCompare(b,'zh-CN'))
 }
 await visit(root,path.basename(root));return entries
}
function registerFolderPicker({ipcMain,dialog},getWindow,trusted){
 let picking=false
 ipcMain.handle('xinshi:choose-translation-folder',async event=>{
  const win=getWindow()
  if(!win||event.sender!==win.webContents||event.senderFrame!==win.webContents.mainFrame||!trusted(event.senderFrame.url)||!win.isFocused())throw Error('请在系统桌面窗口中选择文件夹')
  if(picking)throw Error('正在选择文件夹，请稍候')
  picking=true
  try{
   const result=await dialog.showOpenDialog(win,{title:'选择笔译项目根文件夹',properties:['openDirectory']})
   if(result.canceled||!result.filePaths?.length)return null
   const rootPath=path.resolve(result.filePaths[0])
   if(!path.basename(rootPath))throw Error('请选择具体根文件夹，不要只选择盘符')
   return {rootPath,entries:await enumerate(rootPath)}
  }finally{picking=false}
 })
}
module.exports={enumerate,registerFolderPicker}
