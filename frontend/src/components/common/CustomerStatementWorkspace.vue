<template>
  <section class="statement-workspace" v-loading="loading||saving">
    <p class="statement-help">可选多个月合并导入。对账单修改独立保存，不改变项目数据。同一任务只能归属一份对账单；拖动任务可跨单调配，拖动卡片标题可自由排列。</p>
    <AppForm :model="filters" inline @submit.prevent="importMonths">
      <el-form-item label="账单月份"><el-date-picker v-model="filters.months" type="months" value-format="YYYY-MM" placeholder="选择一个或多个月份" style="width:300px;max-width:100%" /></el-form-item>
      <el-form-item v-if="!clientId" label="生成范围"><el-radio-group v-model="filters.scope"><el-radio value="project">当前项目</el-radio><el-radio value="customer">该客户全部项目</el-radio></el-radio-group></el-form-item>
      <el-form-item><el-checkbox v-model="filters.requiredOnly">仅导入需对账单项目</el-checkbox></el-form-item>
      <el-form-item label="导入到"><el-select v-model="importBoardId" placeholder="首份对账单" clearable style="width:170px"><el-option v-for="board in documents" :key="board.id" :value="board.id" :label="board.name" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" :disabled="!canWrite||!filters.months?.length" @click="importMonths">合并导入所选月份</el-button><el-button @click="load">重新加载</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-if="state" class="workspace-toolbar">
      <el-select v-model="mode" aria-label="对账单订单显示方式" style="width:260px" @change="load"><el-option v-for="option in statementOrderDisplayOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select>
      <el-button :disabled="!canWrite||!documents.length" @click="createBoard">新增一份对账单</el-button>
      <el-button :disabled="!state.revision" @click="openHistory">修改记录 / 恢复</el-button>
      <CustomerStatementSettings />
      <el-select v-model="scale" aria-label="对账单画布缩放" style="width:105px"><el-option v-for="value in [0.4,0.5,0.75,1]" :key="value" :value="value" :label="`${value*100}%`" /></el-select>
      <el-button :disabled="!documents.some(board=>board.statement.rows.length)" @click="download(documents.filter(board=>board.statement.rows.length).map(board=>board.id))">全部下载Excel</el-button>
      <el-button :disabled="!documents.some(board=>board.statement.rows.length)" @click="printBoards(documents.filter(board=>board.statement.rows.length).map(board=>board.id))">全部打印 / PDF</el-button>
    </div>
    <div v-if="selected.length" class="selection-toolbar">
      <span>已选 {{selected.length}} 项任务</span><el-button @click="selected=[]">清空选择</el-button><el-button :disabled="!canWrite" @click="openMove(selected)">调整月份 / 移到另一份</el-button><el-button :disabled="!canWrite" @click="restoreTasks">恢复任务原始内容</el-button>
    </div>
    <el-empty v-if="state&&!documents.length" description="选择账单月份后，合并导入项目任务" />
    <div v-if="documents.length" class="statement-canvas-scroll">
      <div class="statement-canvas-space" :style="{width:`${canvasWidth*scale}px`,height:`${canvasHeight*scale}px`}">
        <div class="statement-canvas" :style="{width:`${canvasWidth}px`,height:`${canvasHeight}px`,transform:`scale(${scale})`}">
          <section v-for="board in documents" :key="board.id" :data-statement-board="board.id" class="statement-board" :class="{'statement-board--drop':dropBoard===board.id}" :style="boardStyle(board)" @dragover.prevent="dropBoard=board.id" @dragleave.self="dropBoard=''" @drop.prevent="dropTasks($event,board)">
            <div class="statement-board-header"><div class="statement-board-handle" @pointerdown="startBoardDrag($event,board)">⠿ {{board.name}}</div><span>任务 {{tasksFor(board.id).length}} 项</span></div>
            <div class="statement-board-actions"><el-button :disabled="!canWrite" @click="editHeader(board)">修改抬头 / 账户 / 印章</el-button><el-button :disabled="!board.statement.rows.length" @click="download([board.id])">Excel</el-button><el-button :disabled="!board.statement.rows.length" @click="printBoards([board.id])">打印 / PDF</el-button></div>
            <div class="statement-board-content"><CustomerStatementPaper :statement="board.statement" interactive :can-write="canWrite&&!saving" :selected="selected" @select="selectTasks" @edit="editRow(board,$event)" @task-pointer="startTaskPointer" /></div>
          </section>
        </div>
      </div>
    </div>
    <div ref="printSource" class="statement-print-source" aria-hidden="true"><div v-for="board in documents" :key="board.id" :data-statement-print="board.id"><CustomerStatementPaper :statement="board.statement" /></div></div>

    <DraggableFormDialog v-model="editVisible" class="statement-edit-dialog" width="min(880px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="closeEdit">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editType==='row'?'修改对账单任务':'修改对账单内容'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="editBody"><AppForm ref="editForm" :model="draft" label-position="top" :disabled="saving">
        <el-form-item v-if="editType==='row'" label="订单号"><ReadonlyField :model-value="editingRow?.order_no" source="auto" /></el-form-item>
        <div class="statement-edit-grid"><el-form-item v-for="field in editingFields" :key="field.key" :label="field.label" :prop="field.key" :rules="field.required?[{required:true,message:`请填写${field.label}`,trigger:'change'}]:[]">
          <template v-if="field.key==='stamp_image'"><img :src="draft.stamp_image" class="statement-edit-stamp" alt="印章预览" /><input type="file" accept="image/png,image/jpeg,image/webp" @change="selectStamp" /></template>
          <el-switch v-else-if="field.key==='tax_included'" v-model="draft.tax_included" active-text="含税" inactive-text="不含税" />
          <el-date-picker v-else-if="field.key==='received_date'" v-model="draft[field.key]" type="date" value-format="YYYY-MM-DD" />
          <el-input v-else v-model="draft[field.key]" :type="field.multiline?'textarea':'text'" :rows="field.multiline?3:undefined" :maxlength="5000" />
        </el-form-item></div>
        <p v-if="editType==='row'" class="statement-help">小计可独立调整。修改数量或单价后，可点击下方按钮按计价数量重新计算。</p>
        <el-button v-if="editType==='row'" @click="recalculate">按数量 × 单价 ÷ 计价数量重算小计</el-button>
      </AppForm></div>
      <template #footer><el-button :disabled="saving" @click="closeEdit()">取消</el-button><el-button type="primary" :loading="saving" @click="saveEdit">确认修改…</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="moveVisible" title="调整账单月份与任务归属" class="statement-edit-dialog" width="min(600px, calc(100vw - 32px))" top="10vh" append-to-body :close-on-click-modal="false">
      <AppForm ref="moveForm" :model="moveDraft" label-position="top"><el-form-item label="所选任务"><span>{{moveIds.length}} 项任务，包含其全部收费明细</span></el-form-item><el-form-item label="目标对账单" prop="board_id" :rules="[{required:true,message:'请选择目标对账单',trigger:'change'}]"><el-select v-model="moveDraft.board_id" style="width:100%"><el-option v-for="board in documents" :key="board.id" :value="board.id" :label="board.name" /></el-select></el-form-item><el-form-item label="目标账单月份" prop="month" :rules="[{required:true,message:'请选择目标月份',trigger:'change'}]"><el-date-picker v-model="moveDraft.month" type="month" value-format="YYYY-MM" /></el-form-item></AppForm>
      <template #footer><el-button @click="moveVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveMove">确认调配…</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="historyVisible" title="对账单修改记录" class="statement-edit-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body>
      <el-alert title="恢复到某次修改前，会撤销该次及其之后的编排与内容修改，并新增一条恢复记录。" type="info" :closable="false" />
      <el-table v-loading="historyLoading" :data="history.items" row-key="id"><el-table-column prop="revision" label="版本" width="70" /><el-table-column prop="actor_name" label="操作人" width="100" /><el-table-column label="时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column><el-table-column prop="action" label="操作" width="170" /><el-table-column label="变更内容" min-width="300"><template #default="{row}"><pre class="statement-history-changes">{{historyText(row.changes)}}</pre></template></el-table-column><el-table-column label="恢复" width="170" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="!canWrite||!row.restorable||saving" @click="restoreHistory(row)">恢复到本次修改前</el-button></template></el-table-column></el-table>
      <el-pagination v-model:current-page="historyPage" :page-size="20" :total="history.total" layout="total, prev, pager, next" @current-change="loadHistory" />
      <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from './AppForm.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import ReadonlyField from './ReadonlyField.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import CustomerStatementSettings from './CustomerStatementSettings.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getStatementWorkspace,getClientStatementWorkspace,importStatementMonths,changeStatementWorkspace,getStatementWorkspaceHistory,exportStatementWorkspace} from '@/api/customerStatements'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {statementOrderDisplayOptions} from '@/utils/statementOrderDisplay'
import {statementPrintStyles} from '@/utils/customerStatementPrint'
import {calculateCustomerPrice} from '@/utils/translationCustomerFinance'
const props=defineProps({projectId:{type:[String,Number],default:''},clientId:{type:[String,Number],default:''},billingMonth:String})
const canWrite=hasPermission('projects:write')
const filters=reactive({months:[props.billingMonth||businessDateTimeInputValue().slice(0,7)],scope:'customer',requiredOnly:true})
const modeStorageKey=`customer-statement-order-display:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const savedMode=localStorage.getItem(modeStorageKey)
const state=ref(null),loading=ref(false),saving=ref(false),error=ref(''),importBoardId=ref(''),mode=ref(statementOrderDisplayOptions.some(option=>option.value===savedMode)?savedMode:'children'),scale=ref(.75),selected=ref([]),dropBoard=ref(''),positions=reactive({})
watch(mode,value=>localStorage.setItem(modeStorageKey,value))
const documents=computed(()=>state.value?.documents||[])
watch(()=>documents.value.length,count=>{scale.value=count>=3?.4:count===2?.5:.75})
const position=board=>positions[board.id]||{x:board.x||0,y:board.y||0}
const canvasWidth=computed(()=>Math.max(980,...documents.value.map(board=>position(board).x+980)))
const canvasHeight=computed(()=>Math.max(740,...documents.value.map(board=>position(board).y+740)))
const boardStyle=board=>({left:`${position(board).x}px`,top:`${position(board).y}px`})
const tasksFor=boardId=>Object.values(state.value?.payload.tasks||{}).filter(task=>task.board_id===boardId)
let sequence=0,controller,disposed=false,drag=null
const frames=new Set()
const printSource=ref()
function apply(data){state.value=data;selected.value=[];if(importBoardId.value&&!data.documents.some(board=>board.id===importBoardId.value))importBoardId.value='';for(const key of Object.keys(positions))delete positions[key]}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await (props.clientId?getClientStatementWorkspace(props.clientId,mode.value,{signal:controller.signal}):getStatementWorkspace(props.projectId,mode.value,{signal:controller.signal}));if(seq===sequence)apply(data)}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'对账单加载失败')}finally{if(seq===sequence)loading.value=false}}
async function confirm(text,title='确认对账单修改'){try{await ElMessageBox.confirm(text,title,{type:'warning',confirmButtonText:'确认并记录',cancelButtonText:'取消'});return true}catch{return false}}
async function mutate(action,data,text){if(saving.value||loading.value||!state.value)return false;const revision=state.value.revision;if(!await confirm(text)||disposed)return false;saving.value=true;error.value='';try{const result=await changeStatementWorkspace(state.value.client_id,{revision,action,data,confirmed:true},mode.value);if(!disposed)apply(result);ElMessage.success('已保存并记录修改历史');return true}catch(e){error.value=getLocalizedErrorMessage(e,'对账单修改失败');return false}finally{saving.value=false}}
async function importMonths(){if(!canWrite||saving.value||!filters.months?.length||!state.value)return;const revision=state.value.revision;const months=[...filters.months];if(!await confirm(`将 ${months.join('、')} 的任务合并导入对账单。已存在的任务保留当前月份和归属，不重复加入。`,'确认合并月份'))return;saving.value=true;try{const data=await importStatementMonths({...(props.clientId?{client_id:props.clientId}:{project_id:props.projectId}),months,required_only:filters.requiredOnly,scope:props.clientId?'customer':filters.scope,revision,board_id:importBoardId.value||null,confirmed:true},mode.value);if(!disposed)apply(data);ElMessage.success(`新增 ${data.imported} 项；${data.existing} 项已存在并保持原归属；${data.excluded||0} 项不需对账单未导入`)}catch(e){error.value=getLocalizedErrorMessage(e,'月份导入失败')}finally{saving.value=false}}
async function createBoard(){let name;try{name=(await ElMessageBox.prompt('输入对账单名称','新增一份对账单',{inputValue:`对账单 ${documents.value.length+1}`,inputValidator:value=>!!value?.trim()||'请输入名称'})).value}catch{return}await mutate('create_board',{name},`新增“${name}”，可将已有任务移动到这份对账单。`)}
function selectTasks(ids,checked){selected.value=checked?[...new Set([...selected.value,...ids])]:selected.value.filter(id=>!ids.includes(id))}
const moveVisible=ref(false),moveForm=ref(),moveIds=ref([]),moveDraft=reactive({board_id:'',month:''})
function openMove(ids,board){moveIds.value=[...new Set(ids)];const task=state.value.payload.tasks[moveIds.value[0]];moveDraft.board_id=board?.id||task?.board_id||documents.value[0]?.id;moveDraft.month=task?.month||filters.months[0]||businessDateTimeInputValue().slice(0,7);moveVisible.value=true}
function dropTasks(event,board){dropBoard.value='';if(!canWrite||saving.value)return;try{const ids=JSON.parse(event.dataTransfer.getData('application/x-statement-tasks'));if(Array.isArray(ids)&&ids.length&&ids.every(id=>state.value.payload.tasks[id]))openMove(ids,board)}catch{}}
let pointerTaskIds=[]
function taskPointerMove(event){dropBoard.value=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-statement-board]')?.dataset.statementBoard||''}
function finishTaskPointer(event){window.removeEventListener('pointermove',taskPointerMove);const board=documents.value.find(item=>item.id===document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-statement-board]')?.dataset.statementBoard);const ids=pointerTaskIds;pointerTaskIds=[];dropBoard.value='';if(board&&ids.length)openMove(ids,board)}
function startTaskPointer(event,ids){if(!canWrite||saving.value||event.button!==0)return;pointerTaskIds=[...ids];window.addEventListener('pointermove',taskPointerMove);window.addEventListener('pointerup',finishTaskPointer,{once:true})}
async function saveMove(){if(!await moveForm.value?.validate().catch(()=>false))return;const target=documents.value.find(board=>board.id===moveDraft.board_id);if(await mutate('move_tasks',{task_ids:[...moveIds.value],...moveDraft},`将 ${moveIds.value.length} 项任务移至“${target.name}”，账单月份改为 ${moveDraft.month}。原对账单中将不再出现这些任务。`))moveVisible.value=false}
async function restoreTasks(){await mutate('restore_task',{task_ids:[...selected.value]},`恢复所选 ${selected.value.length} 项任务首次导入时的内容、月份及对账单归属。`)}
function startBoardDrag(event,board){if(!canWrite||saving.value||event.button!==0)return;event.preventDefault();const original=position(board);drag={id:board.id,startX:event.clientX,startY:event.clientY,original:{...original}};window.addEventListener('pointermove',moveBoard);window.addEventListener('pointerup',endBoard,{once:true})}
function moveBoard(event){if(!drag)return;positions[drag.id]={x:Math.max(0,Math.min(20000,drag.original.x+(event.clientX-drag.startX)/scale.value)),y:Math.max(0,Math.min(20000,drag.original.y+(event.clientY-drag.startY)/scale.value))}}
async function endBoard(){window.removeEventListener('pointermove',moveBoard);const moved=drag;drag=null;if(!moved)return;const next=positions[moved.id];if(!next||Math.abs(next.x-moved.original.x)+Math.abs(next.y-moved.original.y)<4){delete positions[moved.id];return}if(!await mutate('position_board',{board_id:moved.id,...next},'保存此份对账单的新位置？'))delete positions[moved.id]}

const editVisible=ref(false),editType=ref('row'),editingBoard=ref(),editingRow=ref(),draft=reactive({}),editForm=ref(),editBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editBody)
const rowFields=[{key:'received_date',label:'来稿日期'},{key:'project_name',label:'项目名称'},{key:'language_pair',label:'翻译方向'},{key:'quantity',label:'工作量'},{key:'basis',label:'计价方式'},{key:'unit_price',label:'单价'},{key:'unit_size',label:'单价对应数量（每多少单位）'},{key:'unit_label',label:'单价口径文案'},{key:'currency',label:'货币',required:true},{key:'subtotal',label:'小计'},{key:'remarks',label:'备注',multiline:true}]
const headerFields=[{key:'name',label:'对账单名称',required:true},{key:'company',label:'公司抬头'},{key:'title',label:'对账单标题'},{key:'client_name',label:'客户名称'},{key:'client_code',label:'客户编号'},{key:'billing_label',label:'账单月份显示文案（留空按任务月份）'},{key:'tax_included',label:'金额口径标签（金额不自动换算）'},{key:'bank_name',label:'开户行'},{key:'account_name',label:'账户名'},{key:'account_number',label:'账号'},{key:'stamp_image',label:'印章图片'}]
const editingFields=computed(()=>editType.value==='row'?rowFields:headerFields)
let originalDraft=''
function openEdit(type,board,row){editType.value=type;editingBoard.value=board;editingRow.value=row;for(const key of Object.keys(draft))delete draft[key];const values=type==='row'?row:{...board.fields,name:board.name,tax_included:board.tax_included};for(const field of (type==='row'?rowFields:headerFields))draft[field.key]=values[field.key]??'';originalDraft=JSON.stringify(draft);clearFieldSearch();editVisible.value=true}
const editHeader=board=>openEdit('header',board)
const editRow=(board,row)=>openEdit('row',board,row)
async function closeEdit(done){if(saving.value)return;if(JSON.stringify(draft)!==originalDraft&&!await confirm('放弃尚未确认保存的修改？','关闭编辑'))return;if(typeof done==='function')done();else editVisible.value=false}
async function saveEdit(){if(!await editForm.value?.validate().catch(()=>false))return;const old=JSON.parse(originalDraft);const fields=Object.fromEntries(Object.entries(draft).filter(([key,value])=>value!==old[key]));if(!Object.keys(fields).length){editVisible.value=false;return}const names=editingFields.value.filter(field=>Object.hasOwn(fields,field.key)).map(field=>field.label).join('、');const action=editType.value==='row'?'edit_row':'edit_board';const data={board_id:editingBoard.value.id,fields,...(editType.value==='row'?{row_id:editingRow.value._row_id}:{})};if(await mutate(action,data,`确认修改 ${names}？只修改本份对账单，订单号保持不变；修改前内容会保留在记录中。`)){originalDraft=JSON.stringify(draft);editVisible.value=false}}
function recalculate(){const total=calculateCustomerPrice(draft.unit_price,draft.quantity,draft.unit_size);if(total==null)return ElMessage.warning('请填写有效的单价、工作量和大于零的计价数量');draft.subtotal=total}
async function selectStamp(event){const file=event.target.files?.[0];if(!file)return;if(file.size>2000000||!['image/png','image/jpeg','image/webp'].includes(file.type))return ElMessage.warning('请选择2MB以内的PNG、JPG或WebP');draft.stamp_image=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)})}

const historyVisible=ref(false),historyLoading=ref(false),historyPage=ref(1),history=reactive({items:[],total:0})
let historySequence=0
async function loadHistory(){const seq=++historySequence;historyLoading.value=true;try{const data=await getStatementWorkspaceHistory(state.value.client_id,{skip:(historyPage.value-1)*20,limit:20});if(seq===historySequence&&!disposed)Object.assign(history,data)}catch(e){error.value=getLocalizedErrorMessage(e,'修改记录加载失败')}finally{if(seq===historySequence)historyLoading.value=false}}
function openHistory(){historyPage.value=1;historyVisible.value=true;void loadHistory()}
function historyText(value){const names=Object.fromEntries([...rowFields,...headerFields].map(field=>[field.key,field.label]));return JSON.stringify(value,(key,item)=>key==='stamp_image'?'印章图片':item,2).replace(/"([a-z_]+)":/g,(text,key)=>`${names[key]||({before:'修改前',after:'修改后',fields:'字段',order_no:'订单号',month:'月份',board_id:'对账单编号',task_id:'任务编号',months:'月份',added_tasks:'新增任务',existing_tasks_kept:'已有任务保留'}[key])||key}：`)}
async function restoreHistory(row){if(await mutate('restore_history',{history_id:row.id},`恢复至版本 ${row.revision} 修改前？此后所有编排和内容修改将撤销，现状仍会保留在新的恢复记录中。`))void loadHistory()}
async function download(ids){if(!ids.length)return;try{const blob=await exportStatementWorkspace(state.value.client_id,{board_ids:ids,revision:state.value.revision,mode:mode.value});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='客户对账单.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){error.value=getLocalizedErrorMessage(e,'对账单Excel下载失败')}}
function printBoards(ids){const elements=[...(printSource.value?.querySelectorAll('[data-statement-print]')||[])].filter(element=>ids.includes(element.dataset.statementPrint));if(!elements.length)return;const frame=document.createElement('iframe');frame.style.cssText='position:fixed;width:0;height:0;border:0;right:0;bottom:0';frame.title='对账单打印';frames.add(frame);const cleanup=()=>{frames.delete(frame);frame.remove()};frame.srcdoc=`<!doctype html><meta charset="utf-8"><style>${statementPrintStyles}.statement-paper{break-after:page;min-width:0}.statement-paper:last-child{break-after:auto}.statement-ui{display:none}.statement-table th:nth-child(1){width:13%}.statement-table th:nth-child(2){width:8%}.statement-table th:nth-child(3){width:8%}.statement-table th:nth-child(4){width:15%}.statement-table th:nth-child(5){width:9%}.statement-table th:nth-child(6){width:16%}.statement-table th:nth-child(7){width:12%}.statement-table th:nth-child(8){width:9%}.statement-table th:nth-child(9){width:10%}</style>${elements.map(element=>element.innerHTML).join('')}`;frame.onload=async()=>{try{await Promise.all([...frame.contentDocument.images].map(image=>image.decode().catch(()=>{})));frame.contentWindow.addEventListener('afterprint',cleanup,{once:true});frame.contentWindow.focus();frame.contentWindow.print()}catch{cleanup();ElMessage.error('打印窗口打开失败')}};document.body.appendChild(frame)}
watch(()=>[props.clientId,props.projectId],()=>{selected.value=[];editVisible.value=false;moveVisible.value=false;historyVisible.value=false;void load()},{immediate:true})
onBeforeUnmount(()=>{disposed=true;sequence++;historySequence++;controller?.abort();window.removeEventListener('pointermove',moveBoard);window.removeEventListener('pointerup',endBoard);window.removeEventListener('pointermove',taskPointerMove);window.removeEventListener('pointerup',finishTaskPointer);for(const frame of frames)frame.remove()})
</script>
<style scoped>
.statement-workspace{min-width:0}.statement-help{font-size:12px;line-height:1.7;color:var(--el-text-color-secondary)}.workspace-toolbar,.selection-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}.statement-canvas-scroll{overflow:auto;max-height:72vh;border:1px solid var(--el-border-color);background:#eef2f6}.statement-canvas-space{position:relative;min-width:100%}.statement-canvas{position:relative;transform-origin:top left}.statement-board{position:absolute;width:960px;height:720px;background:white;border:1px solid #ccd3de;border-radius:8px;display:flex;flex-direction:column;box-shadow:0 2px 10px #0001}.statement-board--drop{outline:3px solid var(--el-color-primary)}.statement-board-header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px;border-bottom:1px solid #ddd;flex:none}.statement-board-handle{flex:1;cursor:grab;touch-action:none;user-select:none;font-weight:600}.statement-board-handle:active{cursor:grabbing}.statement-board-actions{padding:10px;display:flex;gap:8px;flex-wrap:wrap;flex:none}.statement-board-content{flex:1;min-height:0;overflow:auto}.statement-edit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.statement-edit-stamp{display:block;width:130px;height:130px;object-fit:contain}.statement-history-changes{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto}.statement-print-source{position:fixed;left:-20000px;top:0;width:1050px;pointer-events:none}.statement-workspace .el-pagination{margin-top:12px}.statement-edit-grid .el-date-editor{max-width:100%;width:100%}
:global(.statement-edit-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.statement-edit-dialog .el-dialog__header),:global(.statement-edit-dialog .el-dialog__footer){flex:none}:global(.statement-edit-dialog .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.statement-edit-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}@media(max-width:680px){.statement-edit-grid{grid-template-columns:minmax(0,1fr)}}
</style>
