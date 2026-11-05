<template>
  <section v-loading="loading" class="statement-history" data-dialog-field-search-label="历史对账单">
    <div class="history-toolbar"><el-input v-model="keyword" aria-label="搜索历史对账单" placeholder="搜索对账单名称、账单月份" clearable @input="queueSearch" @keyup.enter="search" /><el-button v-if="selectedId||displayIds.length" @click="selectedId='';displayIds=[]">返回历史列表</el-button></div>
    <div v-if="!selectedId&&!displayIds.length" class="history-toolbar"><el-button :disabled="!selected.length" @click="displayIds=selected.map(board=>board.id)">并列打开所选（{{selected.length}}）</el-button><el-button v-if="!mergeMonths" :disabled="!canWrite||selected.length<2" @click="merge">合并所选</el-button></div>
    <div v-if="mergeMonths&&!selectedId&&!displayIds.length" class="history-toolbar"><span>账单月份</span><el-select v-model="months" multiple clearable placeholder="选择要合并的月份" style="width:340px;max-width:100%"><el-option v-for="month in monthOptions" :key="month" :value="month" :label="month" /></el-select><el-button type="primary" :disabled="!canWrite||mergeCandidates.length<2" @click="merge">合并月份（{{mergeCandidates.length}} 份）</el-button></div>
    <p>{{mergeMonths?'选择月份后，未勾选时合并这些月份的全部对账单；也可勾选指定账单。任务内容及原账单月份保留，合并后可重新命名并保留记录。':'显示该客户所有月份已生成的对账单，与客户管理中的对账单共用数据。'}}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-if="!selectedId&&!displayIds.length" :data="filtered" border row-key="id" empty-text="暂无已生成的历史对账单" @selection-change="selected=$event">
      <el-table-column type="selection" width="45" />
      <el-table-column prop="name" label="对账单名称" min-width="220" show-overflow-tooltip />
      <el-table-column label="账单月份" min-width="180"><template #default="{row}">{{(row.statement?.months||[]).join('、')||'未登记'}}</template></el-table-column>
      <el-table-column label="任务数" width="90"><template #default="{row}">{{row.statement?.rows?.length||0}}</template></el-table-column>
      <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" @click="selectedId=row.id">打开</el-button></template></el-table-column>
    </el-table>
    <CustomerStatementWorkspace v-else :key="`${clientId}:${selectedId}:${displayIds.join(',')}`" :client-id="clientId" :focus-board-id="selectedId" :visible-board-ids="displayIds" @show-boards="ids=>{selectedId='';displayIds=ids}" :billing-month="documents.find(board=>board.id===selectedId)?.statement?.months?.[0]" @loaded="onWorkspaceLoaded" />
    <details v-if="!selectedId" class="all-statements" @toggle="canvasOpened=$event.target.open"><summary>查看全部对账单画布及修改记录</summary><CustomerStatementWorkspace v-if="canvasOpened" :client-id="clientId" @loaded="onWorkspaceLoaded" /></details>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import CustomerStatementWorkspace from './CustomerStatementWorkspace.vue'
import {getClientStatementWorkspace} from '@/api/customerStatements'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {matchesSearchFields} from '@/utils/searchMatching'
import {hasPermission} from '@/utils/permission'
import {ElMessageBox,ElMessage} from 'element-plus'
import {changeStatementWorkspace} from '@/api/customerStatements'
const props=defineProps({clientId:{type:String,required:true},mergeMonths:Boolean})
const canvasOpened=ref(false),months=ref([])
const monthOptions=computed(()=>[...new Set(documents.value.flatMap(board=>board.statement?.months||[]))].sort().reverse())
const selected=ref([]),displayIds=ref([]),revision=ref(0),canWrite=hasPermission('projects:write')
const documents=ref([]),selectedId=ref(''),keyword=ref(''),appliedKeyword=ref(''),loading=ref(false),error=ref('')
const filtered=computed(()=>documents.value.filter(board=>(!props.mergeMonths||!months.value.length||board.statement?.months?.some(month=>months.value.includes(month)))&&matchesSearchFields([board.name,...(board.statement?.months||[])],appliedKeyword.value)))
const mergeCandidates=computed(()=>selected.value.length?filtered.value.filter(board=>selected.value.some(item=>item.id===board.id)):props.mergeMonths&&months.value.length?filtered.value:[])
let controller,sequence=0,timer
function search(){clearTimeout(timer);appliedKeyword.value=keyword.value}
function queueSearch(value){clearTimeout(timer);if(!value.trim())search();else timer=setTimeout(search,400)}
function onWorkspaceLoaded(data){documents.value=data.documents||[];revision.value=data.revision;selected.value=[]}
async function merge(){const candidates=[...mergeCandidates.value];if(candidates.length<2)return;let name;try{name=(await ElMessageBox.prompt('填写合并后的对账单名称；各任务内容和原账单月份保持不变。','合并月份／对账单',{inputValue:months.value.length?`${months.value.join('、')} 对账单`:'',inputValidator:value=>!!value?.trim()||'请填写名称'})).value}catch{return}try{const data=await changeStatementWorkspace(props.clientId,{revision:revision.value,action:'merge_boards',data:{board_ids:candidates.map(board=>board.id),name},confirmed:true},'children');onWorkspaceLoaded(data);selectedId.value=candidates[0].id;ElMessage.success('已合并并保留调整前后记录');window.dispatchEvent(new CustomEvent('translation-statements-changed'))}catch(e){error.value=getLocalizedErrorMessage(e,'合并失败')}}
window.addEventListener('customer-statement-history-refresh',load)
onBeforeUnmount(()=>window.removeEventListener('customer-statement-history-refresh',load))
async function load(){controller?.abort();controller=new AbortController();const seq=++sequence;loading.value=true;error.value='';try{const data=await getClientStatementWorkspace(props.clientId,'children',{signal:controller.signal});if(seq===sequence)onWorkspaceLoaded(data)}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=getLocalizedErrorMessage(e,'历史对账单加载失败')}finally{if(seq===sequence)loading.value=false}}
watch(()=>props.clientId,()=>{documents.value=[];selectedId.value='';displayIds.value=[];selected.value=[];keyword.value='';search();void load()},{immediate:true})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer)})
</script>
<style scoped>
.statement-history{min-width:0}.history-toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.history-toolbar .el-input{width:280px;max-width:100%}p{font-size:12px;color:var(--el-text-color-secondary)}.all-statements{margin-top:16px}.all-statements summary{cursor:pointer;color:var(--el-color-primary);margin-bottom:12px}
</style>
