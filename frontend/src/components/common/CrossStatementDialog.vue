<template>
  <DraggableFormDialog :model-value="modelValue" class="cross-statement-dialog" width="min(1600px, calc(100vw - 32px))" top="4vh" append-to-body destroy-on-close @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="授权客户历史对账单调整" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading||saving">
      <AppForm :model="form" inline>
        <el-form-item label="已授权客户"><el-select v-model="clientIds" multiple filterable placeholder="搜索并选择客户，可并列展示" style="width:420px;max-width:100%"><el-option v-for="client in clients" :key="client.id" :value="client.id" :label="`${client.name} ${client.code||''}`" /></el-select></el-form-item>
        <el-form-item label="归属客户"><el-select v-model="form.target" filterable style="width:220px"><el-option v-for="client in clients.filter(client=>clientIds.includes(client.id))" :key="client.id" :value="client.id" :label="client.name" /></el-select></el-form-item>
        <el-form-item label="新对账单名称"><el-input v-model="form.name" maxlength="100" placeholder="合并或分拆后的名称" /></el-form-item>
      </AppForm>
      <p>勾选账单进行合并；勾选任务进行分拆。拖动任务行可跨账单、跨客户调配。仅显示获准跨客户操作的客户，内容修改另需授权；原客户来源、订单号保持不变。</p>
      <div class="cross-toolbar"><el-button :disabled="!canWrite||!boards.length||!form.target||!form.name.trim()" @click="apply('merge')">合并／转入所选账单（{{boards.length}}）</el-button><el-button :disabled="!canWrite||!tasks.length||!form.target||!form.name.trim()" @click="apply('split')">分拆选中任务为新账单（{{tasks.length}}）</el-button><el-button @click="load">刷新</el-button></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <div class="cross-clients">
        <section v-for="workspace in workspaces" :key="workspace.owner_client_id" class="cross-client"><h3>{{workspace.client_name}}</h3><el-empty v-if="!workspace.documents.length" description="暂无历史对账单，可作为归属客户" />
          <article v-for="board in workspace.documents" :key="board.id" class="cross-board" :class="{'is-drop':dropKey===`${workspace.owner_client_id}:${board.id}`}" :data-cross-client="workspace.owner_client_id" :data-cross-board="board.id" @dragover.prevent @drop.prevent="drop($event,workspace,board)">
            <header><el-checkbox :model-value="boards.some(item=>item.client_id===workspace.owner_client_id&&item.board_id===board.id)" @change="toggleBoard(workspace,board,$event)">{{board.name}}</el-checkbox><el-button link :disabled="!workspace.capabilities?.edit_content||!canWrite" @click="openEdit(workspace,board)">编辑内容</el-button></header>
            <div class="cross-paper"><CustomerStatementPaper :statement="board.statement" interactive :can-write="canWrite" :selected="tasks" @select="toggleTasks" @task-pointer="startPointer" /></div>
          </article>
        </section>
      </div>
    </div>
    <CustomerStatementInlineEditor v-model="editing" :board="editingBoard" :can-write="!!editingWorkspace?.capabilities?.edit_content&&canWrite" :saving="saving" :error="error" @save="saveContent" />
    <template #footer><el-button :disabled="saving" @click="emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {reactive,ref,watch,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import CustomerStatementInlineEditor from './CustomerStatementInlineEditor.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getCrossStatementClients,getCrossStatementWorkspaces,reorganizeCrossStatements} from '@/api/statementAccess'
import {changeStatementWorkspace} from '@/api/customerStatements'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:Boolean}),emit=defineEmits(['update:modelValue','saved'])
const body=ref(),clients=ref([]),clientIds=ref([]),workspaces=ref([]),boards=ref([]),tasks=ref([]),loading=ref(false),saving=ref(false),error=ref(''),editing=ref(false),editingBoard=ref(),editingWorkspace=ref()
const form=reactive({target:'',name:''}),canWrite=hasPermission('projects:write')
const dropKey=ref('');let pointerIds=[]
function stopPointer(){window.removeEventListener('pointermove',pointerMove);window.removeEventListener('pointerup',pointerUp);pointerIds=[];dropKey.value=''}
function pointerMove(event){const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-cross-board]');dropKey.value=target?`${target.dataset.crossClient}:${target.dataset.crossBoard}`:''}
function pointerUp(event){const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-cross-board]');const ids=[...pointerIds];stopPointer();if(target&&ids.length&&props.modelValue){void submit(sources(ids),ids,target.dataset.crossClient,target.dataset.crossBoard)}}
function startPointer(_event,ids){if(!canWrite||saving.value)return;stopPointer();pointerIds=[...ids];window.addEventListener('pointermove',pointerMove);window.addEventListener('pointerup',pointerUp,{once:true})}
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let controller,sequence=0
async function load(){controller?.abort();controller=new AbortController();const seq=++sequence;boards.value=[];tasks.value=[];if(!clientIds.value.length){workspaces.value=[];return}loading.value=true;error.value='';try{const data=await getCrossStatementWorkspaces(clientIds.value,{signal:controller.signal});if(seq===sequence)workspaces.value=data.items||[]}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED'){workspaces.value=[];error.value=getLocalizedErrorMessage(e,'账单加载失败')}}finally{if(seq===sequence)loading.value=false}}
function toggleBoard(workspace,board,value){boards.value=boards.value.filter(item=>item.client_id!==workspace.owner_client_id||item.board_id!==board.id);if(value)boards.value.push({client_id:workspace.owner_client_id,board_id:board.id})}
function toggleTasks(ids,value){tasks.value=value?[...new Set([...tasks.value,...ids])]:tasks.value.filter(id=>!ids.includes(id))}
function sources(ids){return workspaces.value.flatMap(workspace=>workspace.documents.filter(board=>Object.values(workspace.payload.tasks).some(task=>task.board_id===board.id&&ids.includes(task.id))).map(board=>({client_id:workspace.owner_client_id,board_id:board.id})))}
async function submit(selection,ids,target,boardId){const involved=[...new Set([...selection.map(item=>item.client_id),target])];const versions=Object.fromEntries(involved.map(id=>[id,workspaces.value.find(workspace=>workspace.owner_client_id===id)?.revision||0]));try{await ElMessageBox.confirm(`将${ids?ids.length+' 项任务':selection.length+' 份账单'}调配至“${clients.value.find(client=>client.id===target)?.name}”的${boardId?'指定账单':`“${form.name}”新账单`}？保留内容及原客户来源，完整记录操作前后。`,'确认历史账单调整',{type:'warning',confirmButtonText:'确认并记录',cancelButtonText:'取消'})}catch{return}saving.value=true;try{await reorganizeCrossStatements({versions,boards:selection,target_client_id:target,target_board_id:boardId||null,name:form.name,task_ids:ids||null,confirmed:true});ElMessage.success('已调整并保留全程记录');await load();emit('saved');window.dispatchEvent(new CustomEvent('translation-statements-changed'))}catch(e){error.value=getLocalizedErrorMessage(e,'账单调整失败')}finally{saving.value=false}}
function apply(mode){return submit(mode==='merge'?boards.value:sources(tasks.value),mode==='merge'?null:tasks.value,form.target,null)}
function drop(event,workspace,board){if(!canWrite||saving.value)return;try{const ids=JSON.parse(event.dataTransfer.getData('application/x-statement-tasks'));if(Array.isArray(ids)&&ids.length&&ids.every(id=>workspaces.value.some(item=>item.payload.tasks[id])))void submit(sources(ids),ids,workspace.owner_client_id,board.id)}catch{}}
function openEdit(workspace,board){editingWorkspace.value=workspace;editingBoard.value=board;editing.value=true}
async function saveContent(data){try{await ElMessageBox.confirm('确认保存账单内容修改？每项修改保留调整前后、操作人与时间。','保存内容',{type:'warning'})}catch{return}saving.value=true;try{await changeStatementWorkspace(editingWorkspace.value.owner_client_id,{revision:editingWorkspace.value.revision,action:'edit_document',data,confirmed:true},'children');editing.value=false;await load();emit('saved')}catch(e){error.value=getLocalizedErrorMessage(e,'保存失败')}finally{saving.value=false}}
watch(clientIds,()=>{if(!clientIds.value.includes(form.target))form.target=clientIds.value[0]||'';void load()})
watch(()=>props.modelValue,async visible=>{clearFieldSearch();if(!visible){sequence++;controller?.abort();stopPointer();return}try{clients.value=(await getCrossStatementClients()).items||[]}catch(e){error.value=getLocalizedErrorMessage(e,'授权客户加载失败')}},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort();stopPointer()})
</script>
<style>
.cross-statement-dialog{display:flex;flex-direction:column;max-height:92vh;overflow:hidden}.cross-statement-dialog .el-dialog__header,.cross-statement-dialog .el-dialog__footer{flex:none}.cross-statement-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.cross-statement-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color)}.cross-clients{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(520px,100%),1fr));gap:16px}.cross-client{min-width:0}.cross-board{border:1px solid var(--el-border-color);border-radius:6px;margin:12px 0}.cross-board.is-drop{outline:2px solid var(--el-color-primary)}.cross-board header{display:flex;align-items:center;justify-content:space-between;padding:10px;background:var(--el-fill-color-light)}.cross-paper{max-height:560px;overflow:auto}.cross-paper .statement-paper{min-width:950px}.cross-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}.cross-statement-dialog p{font-size:12px;color:var(--el-text-color-secondary)}
</style>
