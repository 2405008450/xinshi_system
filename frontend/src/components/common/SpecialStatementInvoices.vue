<template>
  <section v-loading="loading">
    <template v-if="!editorOnly"><AppForm :model="filters" inline @submit.prevent="load">
      <el-form-item label="账单月份"><el-date-picker v-model="filters.months" type="months" value-format="YYYY-MM" clearable @change="load" /></el-form-item>
      <el-form-item label="是否需发票"><el-select v-model="filters.required" @change="selected=[]"><el-option label="全部" value="all" /><el-option label="需" value="yes" /><el-option label="无需" value="no" /><el-option label="待判断" value="unknown" /></el-select></el-form-item>
      <el-form-item><el-button @click="load">查询</el-button><el-button type="primary" :disabled="!canWrite||!selected.length" @click="requestVisible=true">开票需求</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="visible" row-key="board_id" border max-height="560" @selection-change="selected=$event">
      <el-table-column type="selection" width="45" :selectable="row=>row.invoice_required===true" />
      <el-table-column label="对账单" min-width="320"><template #default="{row}"><details><summary>{{row.statement.statement_number||row.name}} · {{row.statement.client_name}} · {{row.statement.month}}</summary><div class="special-invoice-paper"><CustomerStatementPaper :statement="row.statement" /></div></details></template></el-table-column>
      <el-table-column label="是否需发票" width="110"><template #default="{row}">{{row.invoice_required==null?'待判断':row.invoice_required?'需':'无需'}}</template></el-table-column>
      <el-table-column label="对账单金额" min-width="150"><template #default="{row}">{{amount(row.totals)}}</template></el-table-column>
      <el-table-column label="开票主体" min-width="140"><template #default="{row}">{{invoiceSubjectLabels[row.invoice.subject_key||row.subject_key]||'待选择'}}</template></el-table-column>
      <el-table-column label="发票状态" width="110"><template #default="{row}">{{statusLabels[row.invoice.status||'unissued']}}</template></el-table-column>
      <el-table-column label="操作" width="100" fixed="right"><template #default="{row}"><el-button link type="primary" @click="edit(row)">发票</el-button></template></el-table-column>
    </el-table>
    <InvoiceRequestDialog v-if="requestVisible" special-settlement :statement-refs="selected.map(row=>({client_id:row.client_id,board_id:row.board_id,revision:row.revision}))" :project-ids="[...new Set(selected.flatMap(row=>row.project_ids))]" @close="requestVisible=false" @sent="requestVisible=false;load()" />
    </template><DraggableFormDialog @closed="editorOnly&&emit('close')" v-model="editVisible" class="special-statement-invoice-editor" title="对账单发票" append-to-body width="min(800px, calc(100vw - 32px))" top="5vh">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="对账单发票" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="invoiceBody"><AppForm :model="form" label-position="top"><el-form-item label="对账单"><ReadonlyField :model-value="editing?.statement.statement_number||editing?.name" source="auto" /></el-form-item><el-form-item label="开票主体"><el-select v-model="form.subject_key"><el-option v-for="(label,key) in invoiceSubjectLabels" :key="key" :value="key" :label="label" /></el-select></el-form-item><el-form-item label="发票状态"><el-select v-model="form.status"><el-option v-for="(label,key) in statusLabels" :key="key" :value="key" :label="label" /></el-select></el-form-item><el-form-item label="发票及备注"><ScreenshotInput v-model="form.proofs" type="textarea" allow-invoice-files :invoice-order-no="editing?.statement.statement_number||editing?.name" :rows="4" :maxlength="20000" /></el-form-item></AppForm>
      <el-collapse @change="loadOriginal"><el-collapse-item title="原发票（只读）" name="original"><p v-if="originalLoading">正在加载原发票…</p><p v-else-if="!originals.length">没有已登记的原发票。</p><div v-for="(item,index) in originals" :key="index"><strong>{{item.order_no}} · {{item.kind}} · {{statusLabels[item.status]}}</strong><ScreenshotText :text="item.proofs" invoice-drag :invoice-order-no="item.order_no" /></div></el-collapse-item></el-collapse></div>
      <template #footer><el-button @click="editVisible=false">关闭</el-button><el-button type="primary" :disabled="!canWrite" :loading="saving" @click="save">保存发票</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {computed,onBeforeUnmount,reactive,ref,watch} from 'vue'
import api from '@/api'
import {ElMessage} from 'element-plus'
import {invoiceSubjectLabels,invoicePartiesEvent,connectInvoiceParties,notifyInvoiceParties} from '@/api/invoiceParties'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import AppForm from './AppForm.vue'
import ReadonlyField from './ReadonlyField.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import InvoiceRequestDialog from './InvoiceRequestDialog.vue'
import ScreenshotText from './ScreenshotText.vue'
import ScreenshotInput from './ScreenshotInput.vue'
const props=defineProps({invoiceClientId:String,invoiceClientName:String,initialMonth:String,editorOnly:Boolean,readOnly:Boolean,focusBoardId:String,managerQuery:{type:Object,default:()=>({})}})
const invoiceBody=ref()
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(invoiceBody)
const emit=defineEmits(['close','saved'])
const canWrite=computed(()=>!props.readOnly&&(hasPermission('projects:write')||hasPermission('finance:write')||hasPermission('clients:write'))),filters=reactive({months:props.initialMonth?[props.initialMonth]:[],required:'all'})
const items=ref([]),selected=ref([]),loading=ref(false),saving=ref(false),error=ref(''),requestVisible=ref(false),editVisible=ref(false),editing=ref(null)
const originals=ref([]),originalLoading=ref(false);let originalLoaded=false
async function loadOriginal(names){if(!names.length||originalLoaded||originalLoading.value)return;originalLoading.value=true;try{const data=await api.get(`/translation-statement-workspaces/${editing.value.client_id}/special-invoice-originals/${editing.value.board_id}`);originals.value=data.items||[];originalLoaded=true}catch(e){error.value=getLocalizedErrorMessage(e,'原发票加载失败')}finally{originalLoading.value=false}}
const form=reactive({status:'unissued',proofs:'',subject_key:null}),statusLabels={unissued:'未开票',partial:'部分开票',issued:'已开票'}
const visible=computed(()=>items.value.filter(row=>filters.required==='all'||(row.invoice_required==null?'unknown':row.invoice_required?'yes':'no')===filters.required))
const amount=value=>Object.entries(value||{}).map(([currency,total])=>`${currency} ${total}`).join(' / ')||'待补'
let request,sequence=0
async function load(){request?.abort();const controller=request=new AbortController(),seq=++sequence;loading.value=true;error.value='';try{const data=await api.get('/translation-statement-workspaces/special-invoice-documents',{params:{...props.managerQuery,client_id:props.invoiceClientId||undefined,months:filters.months.length?filters.months:undefined},paramsSerializer:{indexes:null},signal:controller.signal,timeout:60000});if(seq===sequence){items.value=data.items;selected.value=[];if(props.editorOnly&&!editVisible.value){const found=items.value.find(row=>row.board_id===props.focusBoardId);if(found)edit(found);else{ElMessage.warning('对账单已废除或不存在，请刷新需求后核对');emit('close')}}}}catch(e){if(!controller.signal.aborted)error.value=getLocalizedErrorMessage(e,'对账单发票加载失败')}finally{if(seq===sequence)loading.value=false}}
function edit(row){originals.value=[];originalLoaded=false;editing.value=row;Object.assign(form,{status:row.invoice.status||'unissued',proofs:row.invoice.proofs||'',subject_key:row.invoice.subject_key||row.subject_key});editVisible.value=true}
async function save(){saving.value=true;try{await api.put(`/translation-statement-workspaces/${editing.value.client_id}/special-invoice/${editing.value.board_id}`,{revision:editing.value.revision,...form});editVisible.value=false;emit('saved');if(!props.editorOnly)await load();notifyInvoiceParties({kind:'special-settlement',clientId:editing.value.client_id})}catch(e){error.value=getLocalizedErrorMessage(e,'发票保存失败')}finally{saving.value=false}}
watch(()=>[props.invoiceClientId,props.initialMonth,JSON.stringify(props.managerQuery)],()=>{filters.months=props.initialMonth?[props.initialMonth]:[];void load()},{immediate:true})
connectInvoiceParties();window.addEventListener(invoicePartiesEvent,load);window.addEventListener('translation-statements-changed',load)
onBeforeUnmount(()=>{sequence++;request?.abort();window.removeEventListener(invoicePartiesEvent,load);window.removeEventListener('translation-statements-changed',load)})
defineExpose({confirmClose:async()=>!saving.value})
</script>
<style scoped>
.special-invoice-paper{max-height:55vh;overflow-y:scroll;overflow-x:auto;overscroll-behavior:contain;scrollbar-gutter:stable;min-width:0}summary{cursor:pointer}section :deep(.el-select){min-width:130px}
:global(.special-statement-invoice-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.special-statement-invoice-editor>.el-dialog__header),:global(.special-statement-invoice-editor>.el-dialog__footer){flex:none}:global(.special-statement-invoice-editor>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}
</style>
