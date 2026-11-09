import test from 'node:test'
import assert from 'node:assert/strict'
import {pendingChildRows,missingChildStatistics,aggregatePendingStatistics} from '../src/utils/translationChildSubmission.js'

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
