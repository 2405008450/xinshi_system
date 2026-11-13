const path=require('node:path'),fs=require('node:fs/promises'),{randomUUID}=require('node:crypto')
const MAX_BYTES=20*1024*1024
const MAX_INVOICE_BYTES = 10 * 1024 * 1024
const invoiceSignatures = {
 pdf: bytes => bytes.subarray(0, 5).toString() === '%PDF-',
 ofd: bytes => bytes.subarray(0, 4).equals(Buffer.from([0x50, 0x4b, 3, 4])),
 png: bytes => bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
 jpg: bytes => bytes.subarray(0, 3).equals(Buffer.from([255, 216, 255])),
}
function invoiceFile(data) {
 const {name, extension, base64} = data || {}
 if (!Object.hasOwn(invoiceSignatures, extension) || typeof base64 !== 'string' ||
     base64.length > Math.ceil(MAX_INVOICE_BYTES / 3) * 4 || !/^[A-Za-z0-9+/]+={0,2}$/.test(base64)) {
  throw Error('发票附件格式或大小无效')
 }
 const bytes = Buffer.from(base64, 'base64')
 if (bytes.length > MAX_INVOICE_BYTES || !invoiceSignatures[extension](bytes)) throw Error('发票附件格式或大小无效')
 return {name: filename(name || '发票', '.' + extension), bytes}
}
function filename(value,extension){const name=String(value||'客户对账单').replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').replace(/[. ]+$/,'').slice(0,120).replace(/\.(xlsx|pdf)$/i,'');return (name||'客户对账单')+extension}
function decodeFile(data){
 if(!data||typeof data.base64!=='string'||data.base64.length>MAX_BYTES*1.4||!/^[A-Za-z0-9+/]*={0,2}$/.test(data.base64))throw Error('对账单文件格式或大小不正确')
 const bytes=Buffer.from(data.base64,'base64'),pdf=data.format==='pdf';if(bytes.length>MAX_BYTES||bytes.length<4||(pdf?!bytes.subarray(0,5).equals(Buffer.from('%PDF-')):bytes.subarray(0,2).toString()!=='PK'))throw Error(pdf?'请选择生成的PDF对账单文件':'请选择生成的Excel对账单文件')
 return bytes
}
function registerStatementDrag({app,ipcMain,BrowserWindow},getWindow,trusted){
 const files=new Map();let rootPromise
 const authorize=event=>{const win=getWindow();if(!win||event.sender!==win.webContents||event.senderFrame!==win.webContents.mainFrame||!trusted(event.senderFrame.url)||!win.isFocused())throw Error('请在系统桌面窗口操作对账单文件');return win}
 const store=async(name,bytes)=>{
  rootPromise??=fs.mkdtemp(path.join(app.getPath('temp'),'xinshi-statements-'))
  const root=await rootPromise,folder=path.join(root,randomUUID());await fs.mkdir(folder)
  const file=path.join(folder,name);if(!path.resolve(file).startsWith(path.resolve(root)+path.sep))throw Error('文件位置无效')
  await fs.writeFile(file,bytes);const icon=await app.getFileIcon(file);const token=randomUUID();files.set(token,{file,icon});return {token,name}
 }
 ipcMain.handle('xinshi:prepare-statement-file',async(event,data)=>{authorize(event);return store(filename(data?.name,data?.format==='pdf'?'.pdf':'.xlsx'),decodeFile(data))})
 ipcMain.handle('xinshi:prepare-invoice-file', async (event, data) => {
  authorize(event)
  const {name, bytes} = invoiceFile(data)
  return store(name, bytes)
 })
 ipcMain.handle('xinshi:prepare-statement-pdf',async(event,data)=>{
  authorize(event);if(typeof data?.html!=='string'||data.html.length>4*1024*1024)throw Error('对账单打印内容无效或过长')
  const preview=new BrowserWindow({show:false,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,javascript:false,webSecurity:true}})
  try{
   preview.webContents.setWindowOpenHandler(()=>({action:'deny'}))
   const html=`<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:;">${data.html}`
   await preview.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(html))
   return await store(filename(data.name,'.pdf'),await preview.webContents.printToPDF({printBackground:true,displayHeaderFooter:false,landscape:true,pageSize:'A4',preferCSSPageSize:true}))
  }finally{preview.destroy()}
 })
 ipcMain.on('xinshi:drag-statement-file',(event,token)=>{
  try{authorize(event);const file=files.get(token);if(!file)throw Error('请重新准备对账单文件');event.sender.startDrag(file)}catch{/* IPC不接收外部文件路径，也不触发额外窗口。 */}
 })
}
module.exports={registerStatementDrag,filename,decodeFile}
