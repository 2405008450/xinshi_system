const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {enumerate,registerFolderPicker}=require('../folder-picker.cjs')
test('native folder picker returns selected absolute path, hierarchy and empty folders, rejects foreign windows',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'xinshi-folder-'))
 try{
  await fs.mkdir(path.join(root,'资料'));await fs.mkdir(path.join(root,'空目录'));await fs.writeFile(path.join(root,'资料','a.pdf'),'test')
  const entries=await enumerate(root);assert(entries.some(row=>row.relativePath.endsWith('/空目录')&&row.files.length===0))
  let handler,calls=0;const frame={url:'http://localhost:3000/translation-details'},win={isFocused:()=>true,webContents:{mainFrame:frame}}
  registerFolderPicker({ipcMain:{handle:(_name,fn)=>handler=fn},dialog:{showOpenDialog:async()=>{calls++;return {canceled:false,filePaths:[root]}}}},()=>win,url=>url.startsWith('http://localhost:3000/'))
  await assert.rejects(()=>handler({sender:{},senderFrame:frame}),/桌面窗口/)
  const result=await handler({sender:win.webContents,senderFrame:frame})
  assert.equal(result.rootPath,root);assert.equal(calls,1);assert.deepEqual(result.entries,entries)
 }finally{const target=path.resolve(root);assert(target.startsWith(path.resolve(os.tmpdir())+path.sep)&&path.basename(target).startsWith('xinshi-folder-'));await fs.rm(target,{recursive:true,force:true})}
})
