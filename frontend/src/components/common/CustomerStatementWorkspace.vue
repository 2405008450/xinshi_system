<template>
  <section class="statement-workspace" v-loading="loading||saving">
    <el-config-provider size="small">
    <details v-if="$slots['customer-projects']" open class="customer-projects-panel">
      <summary>客户项目<span class="customer-projects-toggle">展开 / 收起</span></summary>
      <slot name="customer-projects" :months="filters.months" :mode="mode" />
    </details>
    <slot name="client-actions" />
    <AppForm class="workspace-generation" :model="filters" :disabled="deleteMode||focusMissing" inline @submit.prevent="importMonths">
      <el-form-item label="账单月份"><ReadonlyField v-if="lockMonth" :model-value="filters.months.join('、')" source="auto" style="width:180px" /><el-date-picker v-else v-model="filters.months" type="months" value-format="YYYY-MM" placeholder="选择一个或多个月份" style="width:210px;max-width:100%" /></el-form-item>
      <el-form-item v-if="!clientId" label="生成范围"><el-radio-group v-model="filters.scope"><el-radio value="project">当前项目</el-radio><el-radio value="customer">该客户全部项目</el-radio></el-radio-group></el-form-item>
      <el-form-item v-if="!projectSelection"><el-checkbox v-model="filters.requiredOnly">仅导入需对账单项目</el-checkbox></el-form-item>
      <el-form-item><el-button type="primary" :disabled="!canWrite||loading||saving||!filters.months?.length" @click="importMonths">生成对账单</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <section v-if="state?.pending_tasks?.length" class="statement-pending">
      <h4>待入账任务（{{state.pending_tasks.length}} 项）</h4>
      <p>以下任务已从原对账单移出，生成目标月份时自动纳入。不会因原订单月份或“仅导入需对账单项目”的筛选而遗漏。</p>
      <el-table :data="state.pending_tasks" border max-height="280" row-key="id"><el-table-column prop="order_no" label="订单号" min-width="160" /><el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip /><el-table-column prop="month" label="目标账单月份" width="130" /><el-table-column prop="actor_name" label="调整人" width="100" /><el-table-column label="调整时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column><el-table-column label="操作" width="180" fixed="right"><template #default="{row}"><el-button link :disabled="!canWrite||saving" @click="openSchedule([row.id])">调整月份</el-button><el-button link :disabled="!canWrite||saving" @click="cancelPending(row)">撤销</el-button></template></el-table-column></el-table>
    </section>
    <div v-if="state" class="workspace-toolbar">
      <BatchDeleteToolbar v-if="canWrite&&(documents.length||deleteMode)" :active="deleteMode" :selected-count="selectedBoardIds.length" :loading="saving" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="deleteBoards" />
      <template v-if="!deleteMode">
      <el-select v-model="mode" aria-label="对账单订单显示方式" style="width:210px" @change="load"><el-option v-for="option in statementOrderDisplayOptions" :key="option.value" :value="option.value" :label="option.label" /></el-select>
      <el-button :disabled="!canWrite||!documents.length" @click="createBoard">新增账单</el-button>
      <el-button :disabled="!state.revision" @click="openHistory">记录 / 恢复</el-button>
      <el-button v-if="!projectSelection" :disabled="!canWrite||!filters.months?.length||focusMissing" @click="importMonths">重新生成</el-button>
      <CustomerStatementSettings /><el-dropdown v-if="!projectSelection" trigger="click" @command="reloadProjects"><el-button>更多操作 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :disabled="loading||saving" command="reload">重新加载</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
      <el-select v-model="scale" aria-label="对账单画布缩放" style="width:85px"><el-option v-for="value in [0.4,0.5,0.75,1]" :key="value" :value="value" :label="`${value*100}%`" /></el-select>
      <el-dropdown :disabled="downloading||!exportableBoardIds.length" trigger="click" @command="exportAll">
        <el-button :loading="downloading" :disabled="downloading||!exportableBoardIds.length">导出 / 打印 ▾</el-button>
        <template #dropdown><el-dropdown-menu><el-dropdown-item command="excel">全部下载 Excel</el-dropdown-item><el-dropdown-item command="pdf">全部下载 PDF</el-dropdown-item><el-dropdown-item command="print" divided>全部打印</el-dropdown-item></el-dropdown-menu></template>
      </el-dropdown>
      </template>
    </div>
    <p class="statement-help workspace-hint">未勾选时使用全部筛选项目；修改仅影响对账单。</p>
    <div v-if="!deleteMode&&selected.length" class="selection-toolbar">
      <span>已选 {{selected.length}} 项任务</span><el-button @click="selected=[]">清空选择</el-button><el-button :disabled="!canWrite" @click="splitSelected">分拆至新对账单</el-button><el-button :disabled="!canWrite" @click="openSchedule(selected)">设为待入账</el-button><el-button :disabled="!canWrite" @click="openMove(selected)">调整月份 / 移到另一份</el-button><el-button :disabled="!canEditContent" @click="restoreTasks">恢复任务原始内容</el-button>
    </div>
    <el-empty v-if="state&&!documents.length" :description="focusBoardId?'该对账单已删除或不存在，可返回对账单管理查看记录':focusMonth?'该客户在此月份尚未生成对账单':'暂无对账单，请筛选或勾选下方项目后点击生成对账单'" />
    <div v-if="documents.length" class="statement-canvas-scroll">
      <div class="statement-canvas-space" :style="{width:`${canvasWidth*scale}px`,height:`${canvasHeight*scale}px`}">
        <div class="statement-canvas" :style="{width:`${canvasWidth}px`,height:`${canvasHeight}px`,transform:`scale(${scale})`}">
          <section v-for="board in documents" :key="board.id" :data-statement-board="board.id" class="statement-board" :class="{'statement-board--drop':dropBoard===board.id}" :style="boardStyle(board)" @dragover.prevent="dropBoard=board.id" @dragleave.self="dropBoard=''" @drop.prevent="dropTasks($event,board)">
            <div class="statement-board-header"><el-checkbox v-if="deleteMode" :model-value="selectedBoardIds.includes(board.id)" :aria-label="`选择对账单：${board.name}`" @update:model-value="value=>selectBoard(board.id,value)">选择</el-checkbox><div class="statement-board-handle" @pointerdown="startBoardDrag($event,board)">⠿ {{board.name}}</div><span>任务 {{tasksFor(board.id).length}} 项</span></div>
            <div v-if="!deleteMode" class="statement-board-actions"><el-button type="primary" plain @click="openInline(board)">{{canEditContent?'放大 / 直接编辑':'放大查看'}}</el-button><el-button :disabled="!canEditContent" @click="editHeader(board)">修改抬头 / 账户 / 印章</el-button><el-button :disabled="!board.statement.rows.length" @click="download([board.id])">Excel</el-button><el-button :disabled="!board.statement.rows.length" @click="printBoards([board.id])">打印</el-button><el-button :disabled="downloading||!board.statement.rows.length" @click="download([board.id],'pdf')">下载 PDF</el-button></div>
            <div v-if="!deleteMode" class="statement-board-actions"><el-button v-if="canEditContent" link :disabled="saving" @click="syncCustomerNotes(board)">更新客户备注</el-button><StatementFileDrag :client-id="state.client_id" :board-id="board.id" :revision="state.revision" :mode="mode" :name="`${board.statement.client_name}-${board.name}`" :disabled="saving||!board.statement.rows.length" :print-html="()=>filePrintHtml(board.id)" /></div>
            <p class="statement-system-meta">客户编号：{{board.statement.client_code||'—'}}（仅系统可见）</p>
            <div class="statement-board-content" @click="clickBoard($event,board)"><CustomerStatementPaper :statement="board.statement" :interactive="!deleteMode" :can-write="canWrite&&!saving&&!deleteMode" :can-edit="canEditContent" :selected="selected" @select="selectTasks" @edit="openInline(board)" @task-pointer="startTaskPointer" @open-order="openOrder" /></div>
          </section>
        </div>
      </div>
    </div>
    <div ref="printSource" class="statement-print-source" aria-hidden="true"><div v-for="board in documents" :key="board.id" :data-statement-print="board.id"><CustomerStatementPaper :statement="board.statement" /></div></div>

    <TranslationProjectEditor v-if="orderEditor" :key="`${orderEditor.rootId}:${orderEditor.orderNo}`" editor-only embedded :editor-project-id="orderEditor.rootId" :editor-order-no="orderEditor.orderNo" @editor-closed="orderEditor=null" />
    <CustomerStatementInlineEditor v-model="inlineVisible" :board="inlineBoard" :can-write="canEditContent" :saving="saving" :error="error" @save="saveInline" @open-order="openOrder" />
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

    <DraggableFormDialog v-model="scheduleVisible" title="设置待入账月份" class="statement-edit-dialog" width="min(600px, calc(100vw - 32px))" top="8vh" append-to-body>
      <AppForm ref="scheduleForm" :model="scheduleDraft" label-position="top"><el-form-item label="所选任务">{{scheduleIds.length}} 项，包含全部收费明细；目标月份尚未生成对账单也可以设置。</el-form-item><el-form-item label="目标账单月份" prop="month" :rules="[{required:true,message:'请选择目标月份',trigger:'change'}]"><el-date-picker v-model="scheduleDraft.month" type="month" value-format="YYYY-MM" /></el-form-item></AppForm>
      <template #footer><el-button @click="scheduleVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveSchedule">确认并记录</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="auditVisible" title="对账单调整前后" class="statement-edit-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body>
      <div v-loading="auditLoading"><el-alert v-if="auditError" :title="auditError" type="error" :closable="false" /><template v-if="auditEntry"><p>{{auditEntry.action}} · 调整人：{{auditEntry.actor_name}} · {{formatBusinessDateTime(auditEntry.created_at)}}</p><StatementAuditChanges :before="auditEntry.before" :after="auditEntry.after" :labels="historyLabels" /></template></div>
      <template #footer><el-button @click="auditVisible=false">关闭</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="historyVisible" title="对账单修改记录" class="statement-edit-dialog" width="min(1100px, calc(100vw - 32px))" top="5vh" append-to-body>
      <el-alert title="恢复到某次修改前，会撤销该次及其之后的编排与内容修改，并新增一条恢复记录。" type="info" :closable="false" />
      <el-table v-loading="historyLoading" :data="history.items" row-key="id"><el-table-column prop="revision" label="版本" width="70" /><el-table-column prop="actor_name" label="操作人" width="100" /><el-table-column label="时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column><el-table-column prop="action" label="操作" width="170" /><el-table-column label="变更内容" min-width="300"><template #default="{row}"><StatementAuditChanges :changes="row.changes" :labels="historyLabels" :boards="state?.payload?.boards" :tasks="state?.payload?.tasks" /></template></el-table-column><el-table-column label="调整前后" width="120"><template #default="{row}"><el-button link @click="viewAudit(row)">查看前后</el-button></template></el-table-column><el-table-column label="恢复" width="170" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="!canWrite||!row.restorable||saving" @click="restoreHistory(row)">恢复到本次修改前</el-button></template></el-table-column></el-table>
      <el-pagination v-model:current-page="historyPage" :page-size="20" :total="history.total" layout="total, prev, pager, next" @current-change="loadHistory" />
      <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
    </DraggableFormDialog>
    </el-config-provider>
  </section>
</template>
<script setup>
import StatementFileDrag from './StatementFileDrag.vue'
import StatementAuditChanges from './StatementAuditChanges.vue'
import {computed,defineAsyncComponent,onBeforeUnmount,reactive,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from './AppForm.vue'
import BatchDeleteToolbar from './BatchDeleteToolbar.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import ReadonlyField from './ReadonlyField.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import CustomerStatementInlineEditor from './CustomerStatementInlineEditor.vue'
import CustomerStatementSettings from './CustomerStatementSettings.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getStatementWorkspace,getClientStatementWorkspace,importStatementMonths,changeStatementWorkspace,getStatementWorkspaceHistory,getStatementWorkspaceHistoryEntry,exportStatementWorkspace,exportStatementWorkspacePdf} from '@/api/customerStatements'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import {statementOrderDisplayOptions} from '@/utils/statementOrderDisplay'
import {statementFileName} from '@/utils/statementFormatting'
import {statementPrintStyles} from '@/utils/customerStatementPrint'
import {calculateCustomerPrice} from '@/utils/translationCustomerFinance'
const TranslationProjectEditor=defineAsyncComponent(()=>import('@/views/project/translation/ProjectDetails.vue'))
const orderEditor=ref(null)
function openOrder(row){if(!row.root_id)return ElMessage.warning('该订单缺少项目关联，无法打开');orderEditor.value={rootId:row.root_id,orderNo:row.order_no}}
const emit=defineEmits(['loaded','show-boards'])
const props=defineProps({lockMonth:Boolean,projectSelection:Function,projectReload:Function,visibleBoardIds:{type:Array,default:()=>[]},focusMonth:{type:String,default:''},focusBoardId:{type:String,default:''},projectId:{type:[String,Number],default:''},clientId:{type:[String,Number],default:''},billingMonth:String})
const canWrite=hasPermission('projects:write')
const canEditContent=computed(()=>canWrite&&state.value?.capabilities?.edit_content===true)
const filters=reactive({months:[props.billingMonth||businessDateTimeInputValue().slice(0,7)],scope:'customer',requiredOnly:true})
const modeStorageKey=`customer-statement-order-display:${localStorage.getItem('user_id')||localStorage.getItem('user_name')||'anonymous'}`
const savedMode=localStorage.getItem(modeStorageKey)
const state=ref(null),loading=ref(false),saving=ref(false),error=ref(''),mode=ref(statementOrderDisplayOptions.some(option=>option.value===savedMode)?savedMode:'children'),scale=ref(.75),selected=ref([]),dropBoard=ref(''),positions=reactive({})
watch(mode,value=>localStorage.setItem(modeStorageKey,value))
const deleteMode=ref(false),selectedBoardIds=ref([])
function enterDeleteMode(){selected.value=[];selectedBoardIds.value=[];deleteMode.value=true}
function exitDeleteMode(){deleteMode.value=false;selectedBoardIds.value=[]}
function selectBoard(id,checked){selectedBoardIds.value=checked?[...new Set([...selectedBoardIds.value,id])]:selectedBoardIds.value.filter(value=>value!==id)}
const documents=computed(()=>{const all=(state.value?.documents||[]).filter(board=>!props.visibleBoardIds.length||props.visibleBoardIds.includes(board.id));return props.lockMonth&&props.billingMonth?all.filter(board=>(board.statement.months||[]).includes(props.billingMonth)):props.focusBoardId?all.filter(board=>board.id===props.focusBoardId):props.focusMonth?all.filter(board=>(board.statement.months||[]).includes(props.focusMonth)):all})
watch(()=>documents.value.length,count=>{scale.value=count>=3?.4:count===2?.5:.75})
const focusMissing=computed(()=>!!(props.focusBoardId||props.focusMonth)&&!!state.value&&!documents.value.length)
watch(()=>props.billingMonth,month=>{if(month)filters.months=[month]})
const position=board=>positions[board.id]||{x:board.x||0,y:board.y||0}
const canvasWidth=computed(()=>Math.max(980,...documents.value.map(board=>position(board).x+980)))
const canvasHeight=computed(()=>Math.max(740,...documents.value.map(board=>position(board).y+740)))
const boardStyle=board=>({left:`${position(board).x}px`,top:`${position(board).y}px`})
const tasksFor=boardId=>Object.values(state.value?.payload.tasks||{}).filter(task=>task.board_id===boardId)
let sequence=0,controller,disposed=false,drag=null
const frames=new Set()
const printSource=ref(),downloading=ref(false)
function apply(data){emit('loaded',data);exitDeleteMode();state.value=data;selected.value=[];for(const key of Object.keys(positions))delete positions[key]}
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const data=await (props.clientId?getClientStatementWorkspace(props.clientId,mode.value,{signal:controller.signal}):getStatementWorkspace(props.projectId,mode.value,{signal:controller.signal}));if(seq===sequence)apply(data)}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'对账单加载失败')}finally{if(seq===sequence)loading.value=false}}
async function reloadProjects(){if(props.projectReload&&await props.projectReload()===false)return;await load()}
async function confirm(text,title='确认对账单修改'){try{await ElMessageBox.confirm(text,title,{type:'warning',confirmButtonText:'确认并记录',cancelButtonText:'取消'});return true}catch{return false}}
async function mutate(action,data,text,confirmAction=()=>confirm(text)){if(saving.value||loading.value||!state.value)return false;const revision=state.value.revision;if(!await confirmAction()||disposed)return false;saving.value=true;error.value='';try{const result=await changeStatementWorkspace(state.value.client_id,{revision,action,data,confirmed:true},mode.value);if(!disposed){apply(result);window.dispatchEvent(new CustomEvent('translation-statements-changed'))}ElMessage.success('已保存并记录修改历史');return true}catch(e){error.value=getLocalizedErrorMessage(e,'对账单修改失败');return false}finally{saving.value=false}}
async function deleteBoards(){
  const ids=[...selectedBoardIds.value];if(!ids.length||!canWrite)return
  const names=documents.value.filter(board=>ids.includes(board.id)).map(board=>board.name).join('、')
  const text=`删除 ${ids.length} 份对账单：${names}？所含任务从当前对账单中移除，可按月份重新生成。删除前的完整内容、操作人和时间会保留，可从修改记录恢复。`
  const confirmBatch=ids.length>1?async()=>{try{await ElMessageBox.prompt(text+'请输入“删除”确认。','批量删除对账单',{type:'warning',confirmButtonText:'确认删除并记录',cancelButtonText:'取消',inputValidator:value=>value==='删除'||'请输入“删除”确认'});return true}catch{return false}}:undefined
  await mutate('delete_boards',{board_ids:ids,...(ids.length>1?{confirmation:'删除'}:{})},text,confirmBatch)
}
async function importMonths(){if(!canWrite||saving.value||!filters.months?.length||!state.value)return;let orderIds;try{if(props.projectSelection){orderIds=await props.projectSelection();if(!orderIds)throw new Error('项目表尚未加载完成')}}catch(e){error.value=getLocalizedErrorMessage(e,'读取项目范围失败');return}const revision=state.value.revision;const months=[...filters.months];if(!await confirm(`将 ${months.join('、')} ${orderIds?`所选/筛选范围（${orderIds.length} 个订单）`:'的任务'}生成对账单，同时自动纳入目标为这些月份的全部待入账任务。已入账任务保持原归属，不重复加入。`,'确认合并月份'))return;saving.value=true;try{const data=await importStatementMonths({...(props.clientId?{client_id:props.clientId}:{project_id:props.projectId}),months,order_ids:orderIds,required_only:orderIds!==undefined?false:filters.requiredOnly,scope:props.clientId?'customer':filters.scope,revision,board_id:props.focusBoardId||(props.focusMonth?documents.value[0]?.id:null)||null,confirmed:true},mode.value);if(!disposed){apply(data);window.dispatchEvent(new CustomEvent('translation-statements-changed'))}ElMessage.success(`新增 ${data.imported} 项；${data.existing} 项已存在并保持原归属；${data.excluded||0} 项不需对账单未导入；自动纳入待入账 ${data.accepted_pending_count||0} 项`)}catch(e){error.value=getLocalizedErrorMessage(e,'月份导入失败')}finally{saving.value=false}}
async function splitSelected(){let name;try{name=(await ElMessageBox.prompt('填写分拆后的对账单名称；保留任务内容与月份。','分拆对账单',{inputValidator:value=>!!value?.trim()||'请填写名称'})).value}catch{return}const before=new Set(state.value.documents.map(board=>board.id));const shown=documents.value.map(board=>board.id);if(await mutate('split_board',{task_ids:[...selected.value],name},`将所选 ${selected.value.length} 项任务分拆为“${name}”，保留原内容并记录前后归属？`)){const added=state.value.documents.filter(board=>!before.has(board.id)).map(board=>board.id);emit('show-boards',[...shown,...added])}}

async function createBoard(){let name;try{name=(await ElMessageBox.prompt('输入对账单名称','新增一份对账单',{inputValue:`对账单 ${documents.value.length+1}`,inputValidator:value=>!!value?.trim()||'请输入名称'})).value}catch{return}await mutate('create_board',{name},`新增“${name}”，可将已有任务移动到这份对账单。`)}
function selectTasks(ids,checked){selected.value=checked?[...new Set([...selected.value,...ids])]:selected.value.filter(id=>!ids.includes(id))}
const auditVisible=ref(false),auditLoading=ref(false),auditError=ref(''),auditEntry=ref(null)
async function viewAudit(row){auditVisible.value=true;auditLoading.value=true;auditEntry.value=null;auditError.value='';try{auditEntry.value=await getStatementWorkspaceHistoryEntry(state.value.client_id,row.id)}catch(e){auditError.value=getLocalizedErrorMessage(e,'记录加载失败')}finally{auditLoading.value=false}}
const scheduleVisible=ref(false),scheduleForm=ref(),scheduleIds=ref([]),scheduleDraft=reactive({month:''})
function openSchedule(ids){scheduleIds.value=[...new Set(ids)];scheduleDraft.month=state.value.payload.tasks[ids[0]]?.month||filters.months[0];scheduleVisible.value=true}
async function saveSchedule(){if(!await scheduleForm.value?.validate().catch(()=>false))return;if(await mutate('schedule_tasks',{task_ids:scheduleIds.value,month:scheduleDraft.month},`将 ${scheduleIds.value.length} 项任务设为 ${scheduleDraft.month} 待入账，从原对账单移出；生成目标月份时自动纳入，并保留调整记录。`))scheduleVisible.value=false}
async function cancelPending(row){await mutate('cancel_pending',{task_ids:[row.id]},`撤销 ${row.order_no} 的待入账调整，恢复至调整前的对账单和月份？`)}
const moveVisible=ref(false),moveForm=ref(),moveIds=ref([]),moveDraft=reactive({board_id:'',month:''})
function openMove(ids,board){moveIds.value=[...new Set(ids)];const task=state.value.payload.tasks[moveIds.value[0]];moveDraft.board_id=board?.id||task?.board_id||documents.value[0]?.id;moveDraft.month=task?.month||filters.months[0]||businessDateTimeInputValue().slice(0,7);moveVisible.value=true}
function dropTasks(event,board){dropBoard.value='';if(!canWrite||saving.value)return;try{const ids=JSON.parse(event.dataTransfer.getData('application/x-statement-tasks'));if(Array.isArray(ids)&&ids.length&&ids.every(id=>state.value.payload.tasks[id]))openMove(ids,board)}catch{}}
let pointerTaskIds=[]
function taskPointerMove(event){dropBoard.value=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-statement-board]')?.dataset.statementBoard||''}
function finishTaskPointer(event){window.removeEventListener('pointermove',taskPointerMove);const board=documents.value.find(item=>item.id===document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-statement-board]')?.dataset.statementBoard);const ids=pointerTaskIds;pointerTaskIds=[];dropBoard.value='';if(board&&ids.length)openMove(ids,board)}
function startTaskPointer(event,ids){if(!canWrite||saving.value||deleteMode.value||event.button!==0)return;pointerTaskIds=[...ids];window.addEventListener('pointermove',taskPointerMove);window.addEventListener('pointerup',finishTaskPointer,{once:true})}
async function saveMove(){if(!await moveForm.value?.validate().catch(()=>false))return;const target=documents.value.find(board=>board.id===moveDraft.board_id);if(await mutate('move_tasks',{task_ids:[...moveIds.value],...moveDraft},`将 ${moveIds.value.length} 项任务移至“${target.name}”，账单月份改为 ${moveDraft.month}。原对账单中将不再出现这些任务。`))moveVisible.value=false}
async function restoreTasks(){await mutate('restore_task',{task_ids:[...selected.value]},`恢复所选 ${selected.value.length} 项任务首次导入时的内容、月份及对账单归属。`)}
function startBoardDrag(event,board){if(!canWrite||saving.value||deleteMode.value||event.button!==0)return;event.preventDefault();const original=position(board);drag={id:board.id,startX:event.clientX,startY:event.clientY,original:{...original}};window.addEventListener('pointermove',moveBoard);window.addEventListener('pointerup',endBoard,{once:true})}
function moveBoard(event){if(!drag)return;positions[drag.id]={x:Math.max(0,Math.min(20000,drag.original.x+(event.clientX-drag.startX)/scale.value)),y:Math.max(0,Math.min(20000,drag.original.y+(event.clientY-drag.startY)/scale.value))}}
async function endBoard(){window.removeEventListener('pointermove',moveBoard);const moved=drag;drag=null;if(!moved)return;const next=positions[moved.id];if(!next||Math.abs(next.x-moved.original.x)+Math.abs(next.y-moved.original.y)<4){delete positions[moved.id];return}if(!await mutate('position_board',{board_id:moved.id,...next},'保存此份对账单的新位置？'))delete positions[moved.id]}

const inlineVisible=ref(false),inlineBoard=ref(null)
let inlineRevision=0
function openInline(board){if(deleteMode.value||saving.value||inlineVisible.value)return;inlineBoard.value=board;inlineRevision=state.value.revision;error.value='';inlineVisible.value=true}
function clickBoard(event,board){if(event.target.closest('button,input,label,.statement-ui'))return;openInline(board)}
async function saveInline(data){
  if(state.value.revision!==inlineRevision){error.value='对账单已变化，请关闭窗口重新打开后编辑';return}
  if(await mutate('edit_document',data,'确认保存这份对账单的全部修改？仅修改对账单，每个字段的修改前后内容、操作人与时间都会记录。'))inlineVisible.value=false
}
const editVisible=ref(false),editType=ref('row'),editingBoard=ref(),editingRow=ref(),draft=reactive({}),editForm=ref(),editBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editBody)
const rowFields=[{key:'received_date',label:'来稿日期'},{key:'project_name',label:'项目名称'},{key:'language_pair',label:'翻译方向'},{key:'quantity',label:'工作量'},{key:'basis',label:'计价方式'},{key:'unit_price',label:'单价'},{key:'unit_size',label:'单价对应数量（每多少单位）'},{key:'unit_label',label:'单价口径文案'},{key:'currency',label:'货币',required:true},{key:'subtotal',label:'小计'},{key:'remarks',label:'备注',multiline:true}]
const headerFields=[{key:'name',label:'对账单名称',required:true},{key:'company',label:'公司抬头'},{key:'title',label:'对账单标题'},{key:'client_name',label:'客户名称'},{key:'client_code',label:'客户编号'},{key:'billing_label',label:'账单月份显示（留空按任务月份）'},{key:'issue_date',label:'账单日期'},{key:'tax_included',label:'金额口径标签（金额不自动换算）'},{key:'bank_name',label:'开户行'},{key:'account_name',label:'账户名'},{key:'account_number',label:'账号'},{key:'stamp_image',label:'印章图片'}]
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
window.addEventListener('customer-statement-history-refresh',load)
window.addEventListener('customer-statement-workspace-reload',reloadProjects)
onBeforeUnmount(()=>{window.removeEventListener('customer-statement-history-refresh',load);window.removeEventListener('customer-statement-workspace-reload',reloadProjects)})
function openHistory(){historyPage.value=1;historyVisible.value=true;void loadHistory()}
const historyLabels=Object.fromEntries([...rowFields,...headerFields].map(field=>[field.key,field.label]))
async function restoreHistory(row){if(await mutate('restore_history',{history_id:row.id},`恢复至版本 ${row.revision} 修改前？此后所有编排和内容修改将撤销，现状仍会保留在新的恢复记录中。`))void loadHistory()}
async function syncCustomerNotes(board){await mutate('sync_customer_notes',{board_id:board.id},'将本对账单备注替换为当前客户说明？客户说明为空时清空备注，内部说明和原项目备注不带入；修改前后会保留记录。')}
const exportableBoardIds=computed(()=>documents.value.filter(board=>board.statement.rows.length).map(board=>board.id))
function exportAll(command){if(command==='print')printBoards(exportableBoardIds.value);else void download(exportableBoardIds.value,command)}
async function download(ids,format='excel'){
  if(!ids.length||downloading.value||!state.value)return
  const boards=documents.value.filter(board=>ids.includes(board.id)),revision=state.value.revision,clientId=state.value.client_id,displayMode=mode.value
  if(!boards.length)return
  downloading.value=true;error.value=''
  try{
    const files=[]
    for(const board of boards){const fetch=format==='pdf'?exportStatementWorkspacePdf:exportStatementWorkspace;const blob=await fetch(clientId,{board_ids:[board.id],revision,mode:displayMode});files.push({blob,name:statementFileName(`${board.statement.client_name}-${board.name}`,format)})}
    for(const file of files){const url=URL.createObjectURL(file.blob),link=document.createElement('a');link.href=url;link.download=file.name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),300000)}
  }catch(e){error.value=getLocalizedErrorMessage(e,format==='pdf'?'对账单PDF下载失败':'对账单Excel下载失败')}
  finally{downloading.value=false}
}
function filePrintHtml(id){const element=printSource.value?.querySelector(`[data-statement-print="${CSS.escape(id)}"]`);return `<style>${statementPrintStyles}.statement-ui{display:none}</style>${element?.innerHTML||''}`}
function printBoards(ids){const elements=[...(printSource.value?.querySelectorAll('[data-statement-print]')||[])].filter(element=>ids.includes(element.dataset.statementPrint));if(!elements.length)return;const frame=document.createElement('iframe');frame.style.cssText='position:fixed;width:0;height:0;border:0;right:0;bottom:0';frame.title='对账单打印';frames.add(frame);const cleanup=()=>{frames.delete(frame);frame.remove()};frame.srcdoc=`<!doctype html><meta charset="utf-8"><title>对账单</title><style>${statementPrintStyles}.statement-paper{break-after:page;min-width:0}.statement-paper:last-child{break-after:auto}.statement-ui{display:none}</style>${elements.map(element=>element.innerHTML).join('')}`;frame.onload=async()=>{try{await Promise.all([...frame.contentDocument.images].map(image=>image.decode().catch(()=>{})));frame.contentWindow.addEventListener('afterprint',cleanup,{once:true});frame.contentWindow.focus();frame.contentWindow.print()}catch{cleanup();ElMessage.error('打印窗口打开失败')}};document.body.appendChild(frame)}
watch(()=>[props.clientId,props.projectId,props.focusBoardId,props.focusMonth],()=>{exitDeleteMode();inlineVisible.value=false;selected.value=[];editVisible.value=false;moveVisible.value=false;historyVisible.value=false;void load()},{immediate:true})
onBeforeUnmount(()=>{disposed=true;sequence++;historySequence++;controller?.abort();window.removeEventListener('pointermove',moveBoard);window.removeEventListener('pointerup',endBoard);window.removeEventListener('pointermove',taskPointerMove);window.removeEventListener('pointerup',finishTaskPointer);for(const frame of frames)frame.remove()})
</script>
<style scoped>
.workspace-generation{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 0 2px}.workspace-generation :deep(.el-form-item){margin:0 0 8px}.workspace-toolbar :deep(.el-button + .el-button){margin-left:0}.workspace-toolbar{padding-top:10px;border-top:1px solid var(--el-border-color-lighter)}.workspace-hint{margin:6px 0 12px}.workspace-toolbar :deep(.el-select){flex-shrink:0}

.customer-projects-panel{margin-bottom:12px;border:1px solid var(--el-border-color);border-radius:6px;background:#fff;min-width:0}.customer-projects-panel>summary{cursor:pointer;padding:12px 16px;font-weight:600;user-select:none}.customer-projects-toggle{float:right;font-size:12px;font-weight:400;color:var(--el-text-color-secondary)}.customer-projects-panel :deep(.statement-client-finance > .el-card__header){display:none}.customer-projects-panel :deep(.statement-client-finance){border:0}

.statement-workspace{min-width:0}.statement-help{font-size:12px;line-height:1.7;color:var(--el-text-color-secondary)}.workspace-toolbar,.selection-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}.statement-canvas-scroll{overflow:auto;max-height:72vh;border:1px solid var(--el-border-color);background:#eef2f6}.statement-canvas-space{position:relative;min-width:100%}.statement-canvas{position:relative;transform-origin:top left}.statement-board{position:absolute;width:960px;height:720px;background:white;border:1px solid #ccd3de;border-radius:8px;display:flex;flex-direction:column;box-shadow:0 2px 10px #0001}.statement-board--drop{outline:3px solid var(--el-color-primary)}.statement-board-header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px;border-bottom:1px solid #ddd;flex:none}.statement-board-handle{flex:1;cursor:grab;touch-action:none;user-select:none;font-weight:600}.statement-board-handle:active{cursor:grabbing}.statement-board-actions{padding:10px;display:flex;gap:8px;flex-wrap:wrap;flex:none}.statement-system-meta{margin:8px 16px;color:var(--el-text-color-secondary);font-size:12px}.statement-board-content{flex:1;min-height:0;overflow:auto}.statement-edit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.statement-edit-stamp{display:block;width:130px;height:130px;object-fit:contain}.statement-history-changes{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto}.statement-print-source{position:fixed;left:-20000px;top:0;width:1050px;pointer-events:none}.statement-workspace .el-pagination{margin-top:12px}.statement-edit-grid .el-date-editor{max-width:100%;width:100%}
:global(.statement-edit-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.statement-edit-dialog .el-dialog__header),:global(.statement-edit-dialog .el-dialog__footer){flex:none}:global(.statement-edit-dialog .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.statement-edit-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}@media(max-width:680px){.statement-edit-grid{grid-template-columns:minmax(0,1fr)}}

.workspace-generation{padding:2px 0;gap:6px}.workspace-generation :deep(.el-form-item){margin:0 0 4px}.workspace-toolbar{margin:4px 0;padding-top:5px;gap:6px}.workspace-hint{font-size:11px;margin:3px 0 6px}.customer-projects-panel{margin-bottom:6px}.customer-projects-panel>summary{padding:8px 12px}.statement-board-header{padding:6px 10px}.statement-board-actions{padding:5px 8px;gap:6px}.statement-board-actions :deep(.el-button + .el-button){margin-left:0}.statement-system-meta{margin:4px 12px}
</style>
