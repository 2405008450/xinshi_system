<template>
  <DraggableFormDialog :model-value="modelValue" class="statement-inline-editor" width="min(1600px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${canWrite?'对账单放大编辑':'对账单放大查看'} · ${board?.name||''}`" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div v-if="draft" ref="body">
      <p class="inline-help">客户编号：{{draft.statement.client_code||'—'}}（仅系统可见）</p>
      <p v-if="canWrite" class="inline-help">点击账单内的文字或单元格直接修改。订单号不可修改；每项任务的“账单月份”可从 A 月改为 B 月，只改变对账单归属月份。保存时逐项记录修改前后内容，不改变项目数据。</p>
      <p v-if="!canWrite" class="inline-help">当前未获该账单所涉及客户的内容修改授权，仅可查看。任务调配、合并与分拆请返回账单管理操作。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <AppForm ref="nameForm" :model="draft" label-position="top"><el-form-item label="对账单名称" prop="name" :rules="[{required:true,whitespace:true,message:'请填写对账单名称',trigger:'blur'}]"><el-input v-model="draft.name" :disabled="!canWrite||saving" maxlength="100" /></el-form-item></AppForm>
      <label v-if="canWrite" class="inline-stamp">更换印章<input type="file" accept="image/png,image/jpeg,image/webp" :disabled="saving" @change="selectStamp" /></label>
      <fieldset :disabled="saving||!canWrite" class="inline-paper-fields"><CustomerStatementPaper :statement="draft.statement" :editable="canWrite" @open-order="emit('open-order',$event)" /></fieldset>
      <p class="inline-help">数量或单价与“小计”均可单独编辑，小计不会自动覆盖。改动后请核对合计。右上角的账单月份仅修改显示文案；跨月调整请返回对账单管理进行调配。</p>
    </div>
    <template #footer><span class="inline-dirty">{{dirty?'有未保存修改':'当前无未保存修改'}}</span><el-button :disabled="saving" @click="close">关闭</el-button><el-button v-if="canWrite" type="primary" :loading="saving" :disabled="!dirty" @click="save">保存修改并记录…</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from './DraggableFormDialog.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import AppForm from './AppForm.vue'
import CustomerStatementPaper from './CustomerStatementPaper.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,board:Object,canWrite:Boolean,saving:Boolean,error:String})
const emit=defineEmits(['update:modelValue','save','open-order'])
const body=ref(),nameForm=ref(),draft=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let baseline=null,signature=''
const dirty=computed(()=>draft.value&&JSON.stringify(draft.value)!==signature)
watch(()=>props.modelValue,visible=>{if(!visible)return;draft.value=JSON.parse(JSON.stringify(props.board));baseline=JSON.parse(JSON.stringify(draft.value));signature=JSON.stringify(draft.value);clearFieldSearch()})
async function canClose(){if(props.saving)return false;if(!dirty.value)return true;try{await ElMessageBox.confirm('对账单有未保存修改，确定放弃？','关闭放大编辑',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'});return true}catch{return false}}
async function close(){if(await canClose())emit('update:modelValue',false)}
async function beforeClose(done){if(await canClose())done()}
const rowKeys=['received_date','project_name','language_pair','quantity','basis','unit_price','unit_size','unit_label','currency','subtotal','remarks','billing_month']
const text=value=>String(value??'')
async function save(){
  if(!await nameForm.value?.validate().catch(()=>false))return
  const current=draft.value.statement,old=baseline.statement,fields={}
  if(draft.value.name!==baseline.name)fields.name=draft.value.name.trim()
  for(const key of ['company','title','client_name','client_code','stamp_image','tax_included','issue_date'])if(current[key]!==old[key])fields[key]=current[key]
  if(current.month!==old.month)fields.billing_label=current.month
  for(const key of ['bank_name','account_name','account_number'])if(current.settings[key]!==old.settings[key])fields[key]=current.settings[key]
  const original=new Map(old.rows.map(row=>[row._row_id,row]))
  const rows=current.rows.map(row=>({row_id:row._row_id,fields:Object.fromEntries(rowKeys.filter(key=>text(row[key])!==text(original.get(row._row_id)?.[key])).map(key=>[key,row[key]]))})).filter(row=>Object.keys(row.fields).length)
  if(!Object.keys(fields).length&&!rows.length)return ElMessage.info('没有需要保存的修改')
  emit('save',{board_id:draft.value.id,fields,rows})
}
async function selectStamp(event){const file=event.target.files?.[0];if(!file)return;if(file.size>2000000||!['image/png','image/jpeg','image/webp'].includes(file.type))return ElMessage.warning('请选择2MB以内的PNG、JPG或WebP');draft.value.statement.stamp_image=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});event.target.value=''}
</script>
<style scoped>.inline-help{font-size:12px;color:var(--el-text-color-secondary);line-height:1.7}.inline-paper-fields{padding:0;margin:12px 0;border:0;min-width:100%;overflow:auto}.inline-paper-fields :deep(.statement-paper){min-width:1380px}.inline-paper-fields :deep(.statement-table th:first-child),.inline-paper-fields :deep(.statement-table td:first-child){min-width:125px;white-space:nowrap}.inline-paper-fields :deep(.statement-table th:nth-child(4)){min-width:160px}.inline-paper-fields :deep(.statement-table th:last-child){min-width:160px}.inline-dirty{font-size:12px;color:var(--el-text-color-secondary);margin-right:auto}.inline-stamp{display:inline-flex;align-items:center;gap:12px;font-size:13px}:global(.statement-inline-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.statement-inline-editor>.el-dialog__header),:global(.statement-inline-editor>.el-dialog__footer){flex:none}:global(.statement-inline-editor>.el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.statement-inline-editor>.el-dialog__footer){display:flex;align-items:center;border-top:1px solid var(--el-border-color);background:#f8fafc}</style>
