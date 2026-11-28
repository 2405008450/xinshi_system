import test from 'node:test'
import assert from 'node:assert/strict'
import {mergeSavedRecord,sameSavedValue} from '../src/utils/savedDataMerge.js'
import * as mergeTools from '../src/utils/savedDataMerge.js'
import {savedConflictFieldLabel,savedConflictText} from '../src/utils/savedConflictPresentation.js'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import {sameSavedFieldValue} from '../src/utils/savedDataMerge.js'
import {reactive,ref,markRaw,unref,isRef,isReadonly} from 'vue'

test('空白组合行不会产生差异，已填写的零单价仍保留',()=>{
 const blank={direction:'中英',currency:'CNY',unit:'天',quantity:1,hours:8,taxPrices:{}}
 assert.equal(sameSavedFieldValue('rates',[blank],[]),true)
 assert.equal(sameSavedFieldValue('rates',[{...blank,amount:0}],[]),false)
 assert.equal(sameSavedFieldValue('overtime',{pricing_mode:'rates',amount:0,currency:'CNY',rates:[]},null),true)
 const model={rates:[blank]},changes=[]
 mergeSavedRecord(model,{rates:[{...blank,amount:100}]},{rates:[]},(...args)=>changes.push(args))
 assert.deepEqual(changes,[])
 assert.equal(savedConflictFieldLabel('rates'),'组合单价')
 assert.equal(savedConflictText('rates',[blank]),'未填写单价')
})
test('未修改字段自动接收最新保存值，snake与camel字段共用规则',()=>{
 const target={id:'one',projectName:'旧名称',projectStatus:'confirmed',remark:'我的草稿'},changes=[]
 mergeSavedRecord(target,{id:'one',project_name:'旧名称',project_status:'confirmed',remark:'旧备注'},{id:'one',project_name:'新名称',project_status:'sent_to_client',remark:'他人保存的备注'},(...args)=>changes.push(args))
 assert.equal(target.projectName,'新名称');assert.equal(target.projectStatus,'sent_to_client');assert.equal(target.remark,'我的草稿');assert.equal(changes.length,1);assert.equal(changes[0][0],'remark')
})
test('没有服务端变化时不动本地输入，未知字段不塞入编辑表单',()=>{
 const target={name:'未保存输入',localOnly:true};mergeSavedRecord(target,{name:'旧值'},{name:'旧值',created_at:'2026-11-05T00:00:00+08:00'})
 assert.deepEqual(target,{name:'未保存输入',localOnly:true})
})
test('列表更新保留现有行引用和草稿，新增删除使用服务端结果',()=>{
 const row={id:'one',projectName:'本地草稿'},target={items:[row,{id:'removed',projectName:'旧',derivedLabel:'显示用字段'}]}
 mergeSavedRecord(target,{items:[{id:'one',project_name:'原值'},{id:'removed',project_name:'旧'}]},{items:[{id:'one',project_name:'服务端'},{id:'new',project_name:'新项目'}]})
 assert.equal(target.items[0],row);assert.equal(row.projectName,'本地草稿');assert.deepEqual(target.items.map(row=>row.id),['one','new']);assert.equal(target.items[1].projectName,'新项目')
})
test('删除存在未保存修改的行时保留输入并提示',()=>{
 const target={items:[{id:'one',name:'未保存'}]},conflicts=[]
 mergeSavedRecord(target,{items:[{id:'one',name:'旧值'}]},{items:[]},(...args)=>conflicts.push(args))
 assert.equal(target.items.length,1);assert.equal(conflicts.length,1)
})
test('嵌套字段独立合并，零金额和空值不混淆',()=>{
 const target={taxPrices:{unitPriceExclTax:0,unitPriceInclTax:20}},conflicts=[]
 mergeSavedRecord(target,{tax_prices:{unit_price_excl_tax:null,unit_price_incl_tax:20}},{tax_prices:{unit_price_excl_tax:12,unit_price_incl_tax:30}},(...args)=>conflicts.push(args))
 assert.equal(target.taxPrices.unitPriceExclTax,0);assert.equal(target.taxPrices.unitPriceInclTax,30);assert.equal(conflicts[0][0],'taxPrices.unitPriceExclTax')
 assert.equal(sameSavedValue(0,null),false);assert.equal(sameSavedValue(0.12,'0.1200'),true)
})

test('更新时间仅差UTC+8标记时采用服务端时间，不影响真正的业务冲突',()=>{
 const target={updatedAt:'2026-11-10T17:15:09.784336',remark:'我的草稿'},conflicts=[]
 mergeSavedRecord(target,{updated_at:'2026-11-10T17:10:00+08:00',remark:'原备注'},{updated_at:'2026-11-10T17:15:09.784336+08:00',remark:'最新备注'},(...args)=>conflicts.push(args))
 assert.equal(target.updatedAt,'2026-11-10T17:15:09.784336+08:00')
 assert.equal(target.remark,'我的草稿');assert.equal(conflicts.length,1);assert.equal(conflicts[0][0],'remark')
})

test('服务端时间未变化时也纠正本地时间格式；不把系统时间视为行内编辑',()=>{
 const timestamp='2026-11-10T17:15:09.784336+08:00'
 const target={updatedAt:timestamp.replace('+08:00','')}
 mergeSavedRecord(target,{updated_at:timestamp},{updated_at:timestamp},()=>assert.fail('系统时间不得冲突'))
 assert.equal(target.updatedAt,timestamp)
 const table={items:[{id:'one',updatedAt:'本地格式',name:'原名'}]}
 mergeSavedRecord(table,{items:[{id:'one',updated_at:timestamp,name:'原名'}]},{items:[]},()=>assert.fail('只差系统时间的行不算未保存业务修改'))
 assert.deepEqual(table.items,[])
})

test('新增单价保存为相同金额时，服务端行编号和金额格式不产生冲突',()=>{
 const local={languagePair:'中→英',metric:'words',unitSize:1,amount:0.22,taxPrices:{unitPriceExclTax:0.22,unitPriceInclTax:0.22}}
 const saved={id:'rate-1',language_pair:'中→英',metric:'words',unit_size:'1.0000',amount:'0.2200',
   tax_prices:{unit_price_excl_tax:'0.2200',unit_price_incl_tax:'0.2200',total_excl_tax:null,total_incl_tax:null},
   quantity:2200,quantity_dimension:'customer',quantity_metric:'words'}
 const target={prices:[local]}
 mergeSavedRecord(target,{prices:[]},{prices:[saved]},()=>assert.fail('相同单价不应提示冲突'))
 assert.equal(target.prices[0],local)
})

test('未持久化的单价行只在双方计价值有分歧时提示冲突',()=>{
 const remote={id:null,language_pair:'中→英',metric:'words',unit_size:'1',amount:'0.2000',quantity:1800}
 const draft={languagePair:'中→英',metric:'words',unitSize:1,amount:0.22,quantity:1800}
 const target={prices:[draft]}
 const changes=[]
 const capture=(...args)=>changes.push(args)
 mergeSavedRecord(target,{prices:[remote]},{prices:[{...remote,quantity:2200}]},capture)
 assert.equal(changes.length,0)
 mergeSavedRecord(target,{prices:[remote]},{prices:[{...remote,amount:'0.2400'}]},capture)
 assert.equal(changes.length,1)
 assert.equal(changes[0][0],'prices')
 assert.equal(target.prices[0].amount,0.22)
})

test('空白译员占位行等于尚未安排，清空及无关状态更新不制造冲突',()=>{
 const empty={translatorId:'',clientSelected:false,customerRating:'',evaluationNote:''}
 const target={interpreterAssignments:[empty],projectStatus:'initial_follow_up'},changes=[]
 mergeSavedRecord(target,{interpreter_assignments:[{id:'old',translator_id:'removed'}],project_status:'initial_follow_up'},{interpreter_assignments:[],project_status:'candidates_provided'},(...args)=>changes.push(args))
 assert.deepEqual(changes,[])
 assert.equal(target.projectStatus,'candidates_provided')
})

test('选择译员保存并自动改变状态，数据库行编号及只读名称不算冲突',()=>{
 const row={translatorId:'person',clientSelected:true,customerRating:'',evaluationNote:''}
 const target={interpreterAssignments:[row],projectStatus:'initial_follow_up'},changes=[]
 const saved={id:'row-id',sequence_no:1,translator_id:'person',translator_name:'测试译员',client_selected:true,customer_rating:null,evaluation_note:null}
 mergeSavedRecord(target,{interpreter_assignments:[],project_status:'initial_follow_up'},{interpreter_assignments:[saved],project_status:'client_selected'},(...args)=>changes.push(args))
 assert.deepEqual(changes,[])
 assert.equal(target.interpreterAssignments[0],row)
 assert.equal(target.projectStatus,'client_selected')
})

test('译员安排真正被双方改动时保留本地，并对人选、客户选定、评价分别保护',()=>{
 for(const changed of [{translator_id:'other'},{client_selected:true},{customer_rating:'satisfied'},{evaluation_note:'他人备注'}]){
  const target={interpreterAssignments:[{translatorId:'mine',clientSelected:false,customerRating:'',evaluationNote:''}]},changes=[]
  mergeSavedRecord(target,{interpreter_assignments:[]},{interpreter_assignments:[{translator_id:'original',...changed}]},(...args)=>changes.push(args))
  assert.equal(changes.length,1)
  assert.equal(target.interpreterAssignments[0].translatorId,'mine')
 }
 const target={interpreterAssignments:[]},changes=[]
 mergeSavedRecord(target,{interpreter_assignments:[{translator_id:'original'}]},{interpreter_assignments:[{translator_id:'other'}]},(...args)=>changes.push(args))
 assert.equal(changes.length,1) // 本地删除不能被他人换人覆盖。
})

test('未改动译员时接收最新安排；已存在的空白误报不再阻止保存',()=>{
 const target={interpreterAssignments:[{translatorId:'original',customerRating:'',evaluationNote:''}]}
 mergeSavedRecord(target,{interpreter_assignments:[{id:'old',translator_id:'original'}]},{interpreter_assignments:[{id:'new',translator_id:'other',translator_name:'新译员'}]},()=>assert.fail('未修改安排不应冲突'))
 assert.equal(target.interpreterAssignments[0].translatorId,'other')
 const source=readFileSync(new URL('../src/utils/savedDataRegistry.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace(/^export /gm,'')
 const ctx={...mergeTools,reactive,ref,markRaw,unref,isRef,isReadonly,model:reactive({interpreterAssignments:[{translatorId:'',clientSelected:false,customerRating:'',evaluationNote:''}]})}
 vm.createContext(ctx)
 vm.runInContext(source+`\nconflicts.set(model,new Map([['interpreterAssignments',{path:'interpreterAssignments',current:model.interpreterAssignments,latest:[],before:[{translatorId:'old'}]}]]));globalThis.result=modelSavedConflicts(model)`,ctx)
 assert.equal(ctx.result.length,0)
})

test('译员冲突展示业务中文，不再显示字段名、空数组或原始JSON',()=>{
 assert.equal(savedConflictFieldLabel('interpreterAssignments'),'译员安排')
 assert.equal(savedConflictText('interpreterAssignments',[]),'尚未安排译员')
 assert.equal(savedConflictText('interpreter_assignments',[{translatorId:''}]),'尚未安排译员')
 const text=savedConflictText('interpreterAssignments',[{translator_id:'person',translator_name:'测试译员',client_selected:true,customer_rating:'satisfied',evaluation_note:'备注'}])
 assert.match(text,/译员 1：测试译员/)
 assert.match(text,/客户选定：是/)
 assert.match(text,/客户评价：满意/)
 assert.match(text,/评价\/备注：备注/)
 assert.equal(text.includes('translator_id'),false)
})

test('时间段只比较业务值，忽略命名、行ID、序号和显示说明',()=>{
 const local=[{scheduledStart:'2026-11-26T09:00:00',scheduledEnd:'2026-11-26T18:00:00',actualStart:'',actualEnd:'',locations:['深圳 地址'],locationDetails:[{countryProvince:'',city:'深圳',address:'地址'}],languageDirections:[{languageIds:['zh','en'],requiredCount:1}]}]
 const saved=[{id:'server-row',project_id:'project',sequence_no:1,scheduled_start:'2026-11-26T01:00:00Z',scheduled_end:'2026-11-26T10:00:00Z',actual_start:null,actual_end:null,locations:['深圳 地址'],location_details:[{country_province:'',city:'深圳',address:'地址'}],language_directions:[{id:'direction-row',source_language_id:'zh',target_language_id:'en',language_ids:['zh','en'],language_labels:['中文','英语'],display:'中文 ↔ 英语',required_count:'1'}]}]
 assert.equal(mergeTools.sameSavedFieldValue('timeRanges',local,saved),true)
 const target={timeRanges:structuredClone(local)},conflicts=[]
 mergeSavedRecord(target,{time_ranges:structuredClone(saved)},{time_ranges:[{...saved[0],id:'regenerated-row'}]},(...args)=>conflicts.push(args))
 assert.equal(conflicts.length,0)
 for(const change of [{scheduled_end:'2026-11-26T11:00:00Z'},{location_details:[{city:'上海',address:'地址'}]},{language_directions:[{language_ids:['zh','ja'],required_count:1}]},{language_directions:[{language_ids:['zh','en'],required_count:2}]}]){
  assert.equal(mergeTools.sameSavedFieldValue('timeRanges',local,[{...saved[0],...change}]),false)
 }
 assert.equal(savedConflictFieldLabel('timeRanges'),'时间段')
 const text=savedConflictText('timeRanges',saved)
 assert.ok(text.includes('预定开始：')&&text.includes('项目地点：深圳 地址')&&text.includes('中文 ↔ 英语'))
 assert.ok(!text.includes('scheduled_start')&&!text.includes('server-row'))
})
