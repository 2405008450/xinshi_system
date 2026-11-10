import test from 'node:test'
import assert from 'node:assert/strict'
import {pendingChildRows,missingChildStatistics,aggregatePendingStatistics,initialChildDetails,inheritPendingLanguage} from '../src/utils/translationChildSubmission.js'

test('同一文件按方向拆单：各方向独立复制母单所有统计，零值有效',()=>{
  const form={sourceFileName:'原文.docx',languagePair:'中文→英语；中文→法语',wordCountMatrix:{company:{words:100},customer:{pages:0},preliminary:{words:120},translatorEstimate:{hours:1.5}}}
  const rows=pendingChildRows(form)
  assert.equal(rows.length,2)
  for(const row of rows){assert.equal(row.wordCountMatrix.company.words,100);assert.equal(row.wordCountMatrix.customer.pages,0);assert.equal(row.wordCountMatrix.preliminary.words,120);assert.equal(row.wordCountMatrix.translatorEstimate.hours,1.5);assert.equal(row.wordCountCopySourceLabel,'母订单')}
  rows[0].wordCountMatrix.company.words=80
  assert.equal(rows[1].wordCountMatrix.company.words,100)
  assert.equal(form.wordCountMatrix.company.words,100)
  assert.equal(rows[0].wordCountCopyBaseline.company.words,100)
  assert.equal(aggregatePendingStatistics(rows).company.words,180)
})

test('确认汇总后重开或新增方向，使用原始复制数值，保留人工修改与主动清空',()=>{
  const form={sourceFileName:'原文.docx',languagePair:'中文→英语；中文→法语；中文→日语',wordCountMatrixSource:'suborder_aggregate',wordCountMatrix:{company:{words:180}},pendingDirectionWordCountMatrix:{company:{words:100}},pendingSubOrderDetails:{'001':{wordCountMatrix:{company:{words:80}}},'002':{wordCountMatrix:{company:{words:null}}}}}
  const rows=pendingChildRows(form)
  assert.deepEqual(rows.map(row=>row.wordCountMatrix.company.words),[80,null,100])
  assert.equal(aggregatePendingStatistics(rows).company.words,180)
})

test('文件子单再次按方向拆分，只复制该文件统计，不套用母单总量',()=>{
  const rows=pendingChildRows({languagePair:'中文→英语；中文→法语',initialSubOrderNamesText:'a.pdf',wordCountMatrix:{company:{words:999}},pendingSubOrderDetails:{'001':{wordCountMatrix:{company:{words:30}}}}})
  assert.equal(rows[1].wordCountMatrix.company.words,30)
  assert.equal(rows[2].wordCountMatrix.company.words,30)
  assert.equal(aggregatePendingStatistics(rows).company.words,60)
})

test('旧版方向预览留下的空矩阵补齐母单统计，不覆盖已有数字',()=>{
  const rows=pendingChildRows({sourceFileName:'原文.docx',languagePair:'中文→英语；中文→法语',wordCountMatrix:{company:{words:100}},pendingSubOrderDetails:{'001':{wordCountMatrix:{company:{words:null}}},'002':{wordCountMatrix:{company:{words:80}}}}})
  assert.deepEqual(rows.map(row=>row.wordCountMatrix.company.words),[100,80])
})

test('按方向拆单默认同上一级订单，保留独立修改和主动清空，明细可提交',()=>{
  const form={languagePair:'中文→英语；中文→法语；中文→日语',originalStoragePath:'D:\\原文目录',networkFilePath:'D:\\旧路径',pendingSubOrderDetails:{'001':{networkFilePath:'D:\\独立路径'},'002':{networkFilePath:''},'003':{networkFilePath:'D:\\原文目录'}}}
  const rows=pendingChildRows(form)
  assert.deepEqual(rows.map(row=>row.networkFilePath),['D:\\独立路径','','同上一级订单'])
  assert.equal(initialChildDetails(rows,form)['003'].networkFilePath,'同上一级订单')
  const nested=pendingChildRows({languagePair:'中文→英语；中文→法语',initialSubOrderNamesText:'a.pdf',pendingSubOrderDetails:{'001':{networkFilePath:'\\\\server\\share\\a.pdf'}}})
  assert.equal(nested[1].networkFilePath,'同上一级订单')
  assert.equal(nested[2].networkFilePath,'同上一级订单')
})

test('子订单预填清理空日期和译员，数字进度转为接口字符串，保留零字数',()=>{
  const form={orderNo:'TP-261110-001',projectStatus:'confirmed',customerDeadlineTime:'2026-11-10T18:00:00+08:00',initialSubOrderNamesText:'a.pdf',languagePair:'中文→英语',pendingSubOrderDefaults:{translatorId:'',translatorAssignmentTime:'',sentToClientTime:'',customerDeadlineTime:'',translatorDeliveryProgress:0,review1Progress:35,wordCountMatrix:{company:{words:0}}}}
  const rows=pendingChildRows(form),before=JSON.stringify(rows)
  const details=initialChildDetails(rows,form)['001']
  assert.equal(details.translatorId,null)
  assert.equal(details.translatorAssignmentTime,null)
  assert.equal(details.sentToClientTime,null)
  assert.equal(details.customerDeadlineTime,null)
  assert.equal(details.translatorDeliveryProgress,'0')
  assert.equal(details.review1Progress,'35')
  assert.equal(details.wordCountMatrix.company.words,0)
  assert.equal(JSON.stringify(rows),before)
})

test('多层子订单只累计叶子统计，不重复计算中间订单，且不修改明细',()=>{
  const form={orderNo:'TP-261108-001',initialSubOrderNamesText:'a.pdf\nb.docx',languagePair:'中文→英语；中文→法语',pendingSubOrderDetails:{
    '001':{wordCountMatrix:{company:{words:999}}},
    '001.001':{wordCountMatrix:{company:{words:10,minutes:30}}},
    '001.002':{wordCountMatrix:{company:{words:20,hours:1}}},
    '002.001':{wordCountMatrix:{company:{words:0}}},
    '002.002':{wordCountMatrix:{customer:{pages:2}}},
  }}
  const rows=pendingChildRows(form),before=JSON.stringify(rows)
  assert.equal(missingChildStatistics(rows).length,0)
  const matrix=aggregatePendingStatistics(rows)
  assert.equal(matrix.company.words,30)
  assert.equal(matrix.company.minutes,90)
  assert.equal(matrix.company.hours,null)
  assert.equal(matrix.customer.pages,2)
  assert.equal(JSON.stringify(rows),before)
})

test('母订单填写字数和预统计不能代替子订单统计；零为有效统计',()=>{
  const rows=pendingChildRows({wordCountMatrix:{company:{words:100}},initialSubOrderNamesText:'a.pdf\nb.pdf',languagePair:'中文→英语',pendingSubOrderDetails:{
    '001':{wordCountMatrix:{preliminary:{words:100}}},
    '002':{wordCountMatrix:{company:{words:0}}},
  }})
  assert.deepEqual(missingChildStatistics(rows).map(row=>row.id),['001'])
  assert.equal(aggregatePendingStatistics(rows).company.words,0)
  assert.equal(aggregatePendingStatistics([]).company.words,null)
})

test('目录草稿按后端顺序预览四级订单、跳过空目录，补充文件接续序号',()=>{
  const form={orderNo:'TP-261108-001',languagePair:'中文→英语',initialSubOrderNamesText:'补充.pdf',pendingFolderImport:{sourceKind:'local',rootPath:'D:\\客户项目',entries:[
    {relativePath:'客户项目',files:['根文件.pdf']},
    {relativePath:'客户项目/一级资料',files:['一级文件.docx']},
    {relativePath:'客户项目/一级资料/二级资料',files:[]},
    {relativePath:'客户项目/一级资料/二级资料/三级资料',files:['末级.xlsx']},
    {relativePath:'客户项目/空资料',files:[]},
  ]},pendingSubOrderDetails:{'002.002.001.001':{wordCountMatrix:{company:{words:30}}}}}
  const rows=pendingChildRows(form)
  assert.deepEqual(rows.map(row=>row.id),['001','002','002.001','002.002','002.002.001','002.002.001.001','003'])
  assert.equal(rows[5].networkFilePath,'D:\\客户项目\\一级资料\\二级资料\\三级资料\\末级.xlsx')
  assert.equal(rows[5].wordCountMatrix.company.words,30)
  assert.equal(rows[1].folderInfo.relativePath,'客户项目/一级资料')
  assert.equal(rows[6].subProjectName,'补充.pdf')
})

test('目录子单方向继承母单，修改后跟随直属上级且保留独立分支，重开一致',()=>{
  const form={orderNo:'TP-261110-999',languagePair:'中文→英语',pendingFolderImport:{rootPath:'D:\\项目',entries:[{relativePath:'项目',files:[]},{relativePath:'项目/资料',files:['a.pdf','b.pdf']} ]}}
  const rows=pendingChildRows(form)
  assert.deepEqual(rows.map(row=>row.languagePair),['中文→英语','中文→英语','中文→英语'])
  rows[2].languagePair='中文→日语'
  rows[0].languagePair='中文→法语'
  inheritPendingLanguage(rows,rows[0].subOrderNo,'中文→英语','中文→法语')
  assert.deepEqual(rows.map(row=>row.languagePair),['中文→法语','中文→法语','中文→日语'])
  form.pendingSubOrderDetails=initialChildDetails(rows,form)
  assert.equal(form.pendingSubOrderDetails['001'].languagePair,'中文→法语')
  assert.equal(form.pendingSubOrderDetails['001.001'].languagePair,undefined)
  assert.equal(form.pendingSubOrderDetails['001.002'].languagePair,'中文→日语')
  assert.deepEqual(pendingChildRows(form).map(row=>row.languagePair),rows.map(row=>row.languagePair))
})
