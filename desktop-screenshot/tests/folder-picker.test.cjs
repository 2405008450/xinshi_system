const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {enumerate,registerFolderPicker}=require('../folder-picker.cjs')
test('native folder picker returns selected absolute path, hierarchy and empty folders, rejects foreign windows',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'xinshi-folder-'))
 try{
  await fs.mkdir(path.join(root,'资料'));await fs.mkdir(path.join(root,'空目录'));await fs.writeFile(path.join(root,'资料','a.pdf'),'test')
  const entries=await enumerate(root);assert(entries.some(row=>row.relativePath.endsWith('/空目录')&&row.files.length===0))
  let calls=0,chosen=root,permission=0;const frame={url:'http://localhost:3000/translation-details'},win={isFocused:()=>true,webContents:{mainFrame:frame}}
  const handlers=new Map()
  registerFolderPicker({ipcMain:{handle:(name,fn)=>handlers.set(name,fn)},dialog:{
   showOpenDialog:async()=>{calls++;return {canceled:false,filePaths:[chosen]}},
   showMessageBox:async()=>({response:permission}),
  }},()=>win,url=>url.startsWith('http://localhost:3000/'))
  const handler=handlers.get('xinshi:choose-translation-folder')
  await assert.rejects(()=>handler({sender:{},senderFrame:frame}),/桌面窗口/)
  const result=await handler({sender:win.webContents,senderFrame:frame})
  assert.equal(result.rootPath,root);assert.equal(calls,1);assert.deepEqual(result.entries,entries)
  const event = {sender:win.webContents,senderFrame:frame}
  const selection=await handler(event, 'local-count')
  const read=handlers.get('xinshi:translation-folder-file')
  const relative=path.basename(root)+'/资料/a.pdf'
  assert.equal(await read(event,selection.folderId,relative,false),4)
  assert.equal((await read(event,selection.folderId,relative,true)).toString(),'test')
  await assert.rejects(()=>read(event,'invalid',relative,true),/不属于/)
  await assert.rejects(()=>read(event,selection.folderId,'../outside.pdf',true),/不属于/)
  if(process.platform==='win32'){
   const single=handlers.get('xinshi:single-translation-source')
   await assert.rejects(()=>single(event,root),/新增母子订单/)
   const file=await single(event,path.join(root,'资料'))
   assert.equal(file.name,'a.pdf')
   assert.equal(file.bytes.toString(),'test')
   permission=1
   assert.equal(await single(event,path.join(root,'资料','a.pdf')),null)
  }
  await assert.rejects(() => handler(event, 'unc'), /请选择 UNC/)
  chosen = '\\\\test-server\\share\\project'
  assert.deepEqual(await handler(event, 'unc'), {rootPath: chosen})
 }finally{const target=path.resolve(root);assert(target.startsWith(path.resolve(os.tmpdir())+path.sep)&&path.basename(target).startsWith('xinshi-folder-'));await fs.rm(target,{recursive:true,force:true})}
})
