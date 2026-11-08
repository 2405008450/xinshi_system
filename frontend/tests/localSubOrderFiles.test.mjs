import test from 'node:test'
import assert from 'node:assert/strict'
import {localSubOrderFiles,localFolderEntries,folderOrderPreview,enumerateFolderHandle} from '../src/utils/localSubOrderFiles.js'

test('本地文件保留完整名称并跳过同订单及同批重复文件',()=>{
  const rows=localSubOrderFiles([{name:'合同.docx'},{name:'合同.docx'},{name:'已有.pdf'},{name:'没有扩展名'}],['已有.pdf'])
  assert.equal(rows.filter(row=>row.status==='create').length,1)
  assert.equal(rows.filter(row=>row.status==='duplicate').length,2)
  assert.equal(rows.find(row=>row.name==='没有扩展名').status,'error')
})
test('文件夹只读取第一层普通业务文件，不包含子目录及系统临时文件',()=>{
  const rows=localSubOrderFiles([{name:'一.pdf',webkitRelativePath:'资料/一.pdf'},{name:'二.pdf',webkitRelativePath:'资料/子目录/二.pdf'},{name:'desktop.ini'},{name:'~$合同.docx'}])
  assert.deepEqual(rows.map(row=>row.name),['一.pdf'])
})
test('超过500条整批拒绝，空选择返回空表',()=>{
  assert.deepEqual(localSubOrderFiles([]),[])
  assert.throws(()=>localSubOrderFiles(Array.from({length:501},(_,i)=>({name:`文件${i}.pdf`}))),/500/)
})

test('根目录为母单，三层目录的文件生成四级，路径保留根目录',()=>{
 const entries=localFolderEntries([{name:'根文件.pdf',webkitRelativePath:'项目/根文件.pdf'},{name:'末级.docx',webkitRelativePath:'项目/一/二/三/末级.docx'}])
 assert.equal(entries.length,4)
 const rows=folderOrderPreview(entries,'D:\\客户\\项目')
 assert.equal(rows[0].level,0)
 assert.equal(rows.find(row=>row.name==='末级.docx').level,4)
 assert.equal(rows.find(row=>row.name==='末级.docx').path,'D:\\客户\\项目\\一\\二\\三\\末级.docx')
 assert.throws(()=>localFolderEntries([{name:'超出.pdf',webkitRelativePath:'根/一/二/三/四/超出.pdf'}]),/四级/)
})

test('原生目录枚举保留空目录并在预览标明不生成订单',async()=>{
 const folder=(name,children)=>({name,kind:'directory',async *values(){yield*children}})
 const handle=folder('项目',[folder('空目录',[]),folder('有文件',[{name:'文档.pdf',kind:'file'}])])
 const entries=await enumerateFolderHandle(handle)
 assert.equal(entries.length,3)
 const rows=folderOrderPreview(entries,'D:\\项目')
 assert.equal(rows.find(row=>row.name==='空目录').empty,true)
 assert.equal(rows.find(row=>row.name==='有文件').empty,false)
 assert.equal(rows.filter(row=>row.level>0&&!row.empty).length,2)
})
