import test from 'node:test'
import assert from 'node:assert/strict'
import {reusableTranslationValues} from '../src/utils/translationProjectReuse.js'

test('复用项目兼容客户全称别名及嵌套档案，同时带出客户身份',()=>{
 const empty={clientId:'',clientName:'',clientShortName:'',clientCode:''}
 const fromAlias=reusableTranslationValues({clientId:'c1',clientFullName:'客户全称',clientShortName:'简称'},empty)
 assert.equal(fromAlias.clientName,'客户全称')
 const fromClient=reusableTranslationValues({client:{id:'c2',client_name:'另一客户全称',client_short_name:'另一简称',client_code:'C002'}},empty)
 assert.equal(fromClient.clientId,'c2');assert.equal(fromClient.clientName,'另一客户全称');assert.equal(fromClient.clientShortName,'另一简称');assert.equal(fromClient.clientCode,'C002')
})

test('reuse copies mother business values without identity, child rows or sending/payment history',()=>{
  const empty={id:'',orderNo:'',sourceFileName:'',clientName:'',customerType:null,customerRequirementSpecial:'',wordCountMatrix:{},customerChargeItems:[],paymentConfirmation:null,initialSubOrderNamesText:'',emailSubjectPreview:'',filePathDraft:null}
  const source={id:'old',orderNo:'TP-261001-001',projectName:'资料.pdf',clientName:'测试客户',customerRequirementSpecial:'要求',wordCountMatrix:{company:{words:250}},customerChargeItems:[{id:'old-rate',itemName:'翻译',unitPrice:0.2}],paymentConfirmation:{paid:true},initialSubOrderNamesText:'旧子订单.pdf',emailSubjectPreview:'旧编号主题'}
  source.customerType='企业客户'
  const result=reusableTranslationValues(source,empty,{id:'old-file',storage_path:'D:\\资料',translation_path:'D:\\译文'})
  assert.equal(result.customerType,'企业客户')
  assert.equal(result.sourceFileName,'资料.pdf');assert.equal(result.clientName,'测试客户')
  assert.equal(result.wordCountMatrix.company.words,250)
  for(const key of ['id','orderNo','paymentConfirmation','initialSubOrderNamesText','emailSubjectPreview'])assert.equal(key in result,false)
  assert.equal(result.customerChargeItems[0].id,undefined);assert.equal(result.filePathDraft.storage_path,'D:\\资料')
  result.wordCountMatrix.company.words=1;assert.equal(source.wordCountMatrix.company.words,250)
})
