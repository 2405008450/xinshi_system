import {paymentDetailsForm,paymentDetailsPayload,paymentDetailsSignature} from '../src/utils/paymentDetails.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
import {ref,reactive,computed,watch,nextTick} from 'vue'
import {paymentConfirmationForm,fixFirstDepositStage,clearPaymentSelection} from '../src/utils/paymentConfirmation.js'

const read=path=>readFileSync(new URL(path,import.meta.url),'utf8')
const dialog=read('../src/components/common/ProjectPaymentDialog.vue')
const finance=read('../src/views/project/translation/CustomerFinance.vue')
const match=read('../src/components/common/FullPaymentMatchFields.vue')
const flush=async()=>{for(let i=0;i<6;i++){await Promise.resolve();await nextTick()}}

test('全款总价异步加载及保存通知刷新不清空核对键，不制造未保存草稿',async()=>{
  let resolve
  const changes=[],stops=[]
  const ctx={ref,computed,paymentConfirmationForm,
    watch:(...args)=>{const stop=watch(...args);stops.push(stop);return stop},
    props:reactive({modelValue:paymentConfirmationForm({isPaid:true,paymentOption:'full',fullPaymentAmount:500,fullPaymentTotalKey:'billing:CNY'}),projectId:'p1',draftTotals:null}),
    emit:(_event,value)=>changes.push(value),api:{get:()=>new Promise(done=>{resolve=done})},
    window:{addEventListener(){}},paymentChangeEvent:'payment',AbortController,
    getLocalizedErrorMessage:e=>e.message,onBeforeUnmount(){}}
  vm.createContext(ctx)
  const script=match.split('<script setup>')[1].split('</script>')[0].replace(/^import .*$/gm,'')
    .replace(/^const props=defineProps.*$/gm,'').replace(/^const emit=defineEmits.*$/gm,'')
  vm.runInContext(script,ctx)
  assert.equal(changes.length,0)
  resolve({items:[{key:'billing:CNY',currency:'CNY',amount:'500',label:'计费总价'}]})
  await flush();assert.equal(changes.length,0)
  ctx.onPaymentChanged({detail:{projectId:'p1'}})
  await flush();assert.equal(changes.length,0)
  resolve({items:[{key:'billing:CNY',currency:'CNY',amount:'600',label:'计费总价'}]})
  await flush();assert.equal(changes.length,0)
  for(const stop of stops)stop()
})

test('查看窗口在保存通知后刷新列表，不再加载可编辑的付款副本',()=>{
  const calls=[],ctx={props:{modelValue:true},searchProjects:keyword=>calls.push(keyword),projectKeyword:ref('订单')}
  vm.createContext(ctx)
  vm.runInContext(dialog.slice(dialog.indexOf('function onExternalPayment('),dialog.indexOf('connectPaymentSync();window.addEventListener')),ctx)
  ctx.onExternalPayment({detail:{projectId:'p1'}})
  assert.deepEqual(calls,['订单'])
  ctx.props.modelValue=false;ctx.onExternalPayment({detail:{projectId:'p1'}})
  assert.deepEqual(calls,['订单'])
})

test('关联付款保存同步价格窗口与项目表单，并保留未保存价格',async()=>{
  const previous=paymentConfirmationForm({revision:1,isPaid:true,paymentOption:'deposit'})
  const current=paymentConfirmationForm({revision:2,isPaid:true,paymentOption:'full',fullPaymentAmount:500})
  const before=Array(16).fill(null);before[8]=previous
  const editor=ref({rootId:'p1',adjustedTotal:600,paymentConfirmation:previous})
  const ctx={paymentDetailsSignature,originalPaymentDetails:ref('[]'),editor,original:ref(JSON.stringify(before)),originalPaymentConfirmation:ref(JSON.stringify(previous)),saveError:ref(''),
    paymentConfirmationInput:value=>value,documentParent:ref({paymentConfirmation:previous}),localPaymentParent:ref(null),paymentConfirmationForm,
    rebaseEditorAfterLibrary:async()=>{},emit(){},getLocalizedErrorMessage:e=>e.message}
  vm.createContext(ctx)
  vm.runInContext(finance.slice(finance.indexOf('async function onLinkedPaymentSaved('),finance.indexOf('watch(()=>[filters.projectStatus')),ctx)
  await ctx.onLinkedPaymentSaved({confirmation:current})
  assert.equal(editor.value.paymentConfirmation.revision,2)
  assert.equal(ctx.documentParent.value.paymentConfirmation.fullPaymentAmount,500)
  assert.equal(JSON.parse(ctx.original.value)[8].revision,2)
  assert.equal(editor.value.adjustedTotal,600)
})

test('本窗口保存通过回调同步一次，其他窗口的保存通过广播同步',()=>{
  const calls=[]
  const ctx={financePaymentSource:'editor',onPaymentSaved:result=>calls.push(result)}
  vm.createContext(ctx)
  vm.runInContext(finance.slice(finance.indexOf('function onPaymentChanged('),finance.indexOf('async function onLinkedPaymentSaved(')),ctx)
  for(const source of ['editor','editor-management','editor-linked'])ctx.onPaymentChanged({detail:{projectId:'p1',source}})
  assert.equal(calls.length,0)
  ctx.onPaymentChanged({detail:{projectId:'p1',source:'other-window',confirmation:{revision:3}}})
  assert.equal(calls.length,1);assert.equal(calls[0].confirmation.revision,3)
})
