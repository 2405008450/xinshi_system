const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path')
const {registerStatementDrag,filename,decodeFile}=require('../statement-drag.cjs')
test('原生文件拖出只接受生成的文件令牌，不接受任意路径',async()=>{
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'xinshi-drag-test-')),handlers={},listeners={},frame={url:'http://localhost:3000/'},dragged=[]
 const contents={mainFrame:frame,startDrag:item=>dragged.push(item)},window={webContents:contents,isFocused:()=>true}
 registerStatementDrag({app:{getPath:()=>temp,getFileIcon:async()=>({icon:true})},ipcMain:{handle:(name,fn)=>handlers[name]=fn,on:(name,fn)=>listeners[name]=fn}},()=>window,url=>url===frame.url)
 const event={sender:contents,senderFrame:frame},data={name:'客户/对账单',base64:Buffer.from('PK\x03\x04test-fixture').toString('base64')}
 try{
  const file=await handlers['xinshi:prepare-statement-file'](event,data);assert.equal(file.name,'客户_对账单.xlsx')
  const pdf=await handlers['xinshi:prepare-statement-file'](event,{...data,format:'pdf',base64:Buffer.from('%PDF-1.7 test-fixture').toString('base64')});assert.equal(pdf.name,'客户_对账单.pdf')
  assert.equal((await fs.readFile((()=>{listeners['xinshi:drag-statement-file'](event,pdf.token);return dragged.pop().file})())).toString(),'%PDF-1.7 test-fixture')
  assert.throws(()=>decodeFile({...data,format:'pdf'}),/PDF/)
  listeners['xinshi:drag-statement-file'](event,file.token);assert.equal(dragged.length,1);assert.ok(dragged[0].file.startsWith(temp+path.sep));assert.equal((await fs.readFile(dragged[0].file)).toString(),'PK\x03\x04test-fixture')
  listeners['xinshi:drag-statement-file'](event,'C:\\Windows\\secret');assert.equal(dragged.length,1)
  await assert.rejects(handlers['xinshi:prepare-statement-file']({...event,senderFrame:{url:frame.url}},data),/系统桌面窗口/)
  const invoice = await handlers['xinshi:prepare-invoice-file'](event, {
    name:'TP-123-发票-1',extension:'ofd',base64:data.base64,
  })
  assert.equal(invoice.name,'TP-123-发票-1.ofd')
  listeners['xinshi:drag-statement-file'](event,invoice.token)
  assert.deepEqual(await fs.readFile(dragged.at(-1).file),Buffer.from(data.base64,'base64'))
  await assert.rejects(handlers['xinshi:prepare-invoice-file'](event,{...data,extension:'exe'}),/格式/)
  await assert.rejects(handlers['xinshi:prepare-invoice-file'](event,{...data,extension:'pdf'}),/格式/)
  assert.throws(()=>decodeFile({base64:Buffer.from('arbitrary').toString('base64')}),/Excel/)
  assert.equal(filename('../test.pdf','.pdf'),'.._test.pdf')
 }finally{if(path.resolve(temp).startsWith(path.resolve(os.tmpdir())+path.sep)&&path.basename(temp).startsWith('xinshi-drag-test-'))await fs.rm(temp,{recursive:true,force:true})}
})
