import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {pathToFileURL} from 'node:url'
import {reactive} from 'vue'
const source=(await readFile(new URL('../src/utils/windowUnsavedState.js',import.meta.url),'utf8')).replace("from 'vue'",`from '${new URL('../node_modules/vue/index.mjs',import.meta.url).href}'`).replace("from './savedDataMerge'",`from '${new URL('../src/utils/savedDataMerge.js',import.meta.url).href}'`)
const adjustedSource=source.replace("from './interpretationRateGroups.js'",`from '${new URL('../src/utils/interpretationRateGroups.js',import.meta.url).href}'`)
const api=await import('data:text/javascript;base64,'+Buffer.from(adjustedSource).toString('base64'))
globalThis.localStorage={getItem:()=> 'test-owner'};globalThis.CSS={escape:v=>v}
let uid=0
function setup(){
 const root={matches:()=>false,querySelector:()=>null,getAttribute:()=>null},element={isConnected:true,closest:()=>root,matches:()=>false,querySelector:()=>null,getAttribute:()=>null}
 const model=reactive({id:'one',name:'saved',remarks:null}),instance={uid:++uid}
 const fields=['name','remarks'].map(prop=>({prop,label:prop,$el:{contains:target=>target.field===prop}}))
 api.bindUnsavedForm(instance,model,{root:()=>element,fields:()=>fields,excluded:()=>false});api.beginUnsavedModel(model,model)
 const touch=field=>api.touchUnsavedForm(instance,{target:{field,closest:()=>true}})
 return {model,root,instance,touch,items:()=>api.windowUnsavedItems(root)}
}
test('loading and automatic filling are not unsaved edits',()=>{const f=setup();f.model.name='loaded';f.model.remarks='auto';assert.equal(f.items().length,0)})
test('editing then reverting uses the loaded value as baseline',()=>{const f=setup();f.model.name='loaded';f.touch('name');f.model.name='edited';assert.equal(f.items().length,1);f.model.name='loaded';assert.equal(f.items().length,0)})
test('null and empty text do not produce false edits',()=>{const f=setup();f.touch('remarks');f.model.remarks='';assert.equal(f.items().length,0)})

test('opening an empty select and normalizing its empty array is not an edit',()=>{
 const f=setup();f.model.languageIds=undefined;api.beginUnsavedModel(f.model,f.model)
 f.touch('languageIds');f.model.languageIds=[];assert.equal(f.items().length,0)
 f.touch('languageIds');f.model.languageIds=[''];assert.equal(f.items().length,0)
 f.model.languageIds=[]
 f.touch('languageIds');f.model.languageIds.push('selected-language');assert.equal(f.items().length,1)
})

test('blank rate rows and an enabled but unfilled overtime section are not new content',()=>{
 const f=setup();Object.assign(f.model,{rates:[],has_overtime:false,overtime:null});api.beginUnsavedModel(f.model,f.model)
 f.touch('rates');f.model.rates.push({direction:'中英',currency:'CNY',unit:'天',quantity:1,hours:8,taxPrices:{}})
 assert.equal(f.items().length,0)
 f.touch('has_overtime');f.model.has_overtime=true;f.model.overtime={pricing_mode:'rates',rates:[],currency:'CNY',amount:0}
 assert.equal(f.items().length,0)
 f.touch('rates');f.model.rates[0].taxPrices.unitPriceExclTax=100
 assert.equal(f.items().length,1)
})
test('successful save clears the submitted changes while failure keeps them',()=>{const f=setup();f.touch('name');f.model.name='edited';const save=api.captureUnsavedSave({method:'put',url:'/projects/one',data:{name:'edited'}});api.completeUnsavedSave(save,{saved:false});assert.equal(f.items().length,1);api.completeUnsavedSave(save,{});assert.equal(f.items().length,0)})
test('late save response cannot clear edits made after the request',()=>{const f=setup();f.touch('name');f.model.name='first';const save=api.captureUnsavedSave({method:'put',url:'/projects/one',data:{name:'first'}});f.model.name='second';api.completeUnsavedSave(save,{});assert.equal(f.items().length,1)})
test('unlabelled controls track actual delayed model changes',()=>{const f=setup();f.touch('unknown');assert.equal(f.items().length,0);f.model.name='picked';assert.equal(f.items().length,1)})
test('autosaved drafts preserve evidence of real unsaved edits',()=>{const f=setup();f.touch('name');f.model.name='pending';const state=api.unsavedDraftState(f.model);const next=setup();next.model.name='pending';api.restoreUnsavedDraftState(next.model,state);assert.equal(next.items().length,1)})
