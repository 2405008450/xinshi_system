<template>
  <DraggableFormDialog v-model="visible" width="min(1600px, calc(100vw - 32px))" top="5vh" append-to-body class="talent-quick-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" title="快速登记人才 · 表格录入" v-model="fieldSearchKeyword" placeholder="搜索字段或行号" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <AppForm ref="formRef" :model="form" :disabled="saving" label-position="top" @submit.prevent="save">
        <div class="quick-type-selection">
          <el-form-item label="姓名类型（选1～2种）" prop="nameKinds" :rules="selectionRules"><el-select v-model="form.nameKinds" multiple :multiple-limit="2"><el-option v-for="field in quickNameFields" :key="field.key" :value="field.key" :label="field.label" /></el-select></el-form-item>
          <el-form-item label="联系方式类型（选1～2种，含邮箱）" prop="contactKinds" :rules="selectionRules"><el-select v-model="form.contactKinds" multiple :multiple-limit="2"><el-option v-for="field in quickContactFields" :key="field.key" :value="field.key" :label="field.label" /></el-select></el-form-item>
        </div>
        <div class="quick-row-toolbar"><span>每行一位人才，Tab 或方向键切换单元格；最多100行。</span><div><el-button :disabled="saving || form.rows.length>=100" @click="addRows(1)">新增一行</el-button><el-input-number v-model="addCount" :min="1" :max="Math.max(1,100-form.rows.length)" :precision="0" step-strictly controls-position="right" aria-label="新增行数" :disabled="saving || form.rows.length>=100" /><el-button :disabled="saving || form.rows.length>=100" @click="addRows(addCount)">批量新增</el-button></div></div>
        <div class="quick-grid-scroll"><table class="quick-grid" @keydown="handleTableArrowNavigation">
          <thead><tr><th class="quick-index">序号</th><th v-for="field in selectedFields" :key="field.key" class="quick-field">{{field.label}}</th><th v-for="group in evaluationGroups" :key="group.key" class="quick-rating">{{group.label}}</th><th class="quick-actions">操作</th></tr></thead>
          <tbody><tr v-for="(row,index) in form.rows" :key="row._key" data-dialog-field-search-group :class="{'quick-row-error':row._error}">
            <td class="quick-index"><strong data-dialog-field-search-group-title>第 {{index+1}} 行</strong></td>
            <td v-for="field in selectedFields" :key="field.key"><el-form-item :label="field.label" :prop="`rows.${index}.${field.key}`" :rules="fieldRules(field)"><GridInput v-model="row[field.key]" :maxlength="255" :aria-label="`第${index+1}行${field.label}`" /></el-form-item></td>
            <td v-for="group in evaluationGroups" :key="group.key"><el-form-item :label="group.label" :prop="`rows.${index}.${group.key}Level`"><el-select v-model="row[`${group.key}Level`]" clearable placeholder="待评价"><el-option v-for="level in levels" :key="level.value" :value="level.value" :label="level.label" /></el-select></el-form-item><TalentEvaluationMeta class="quick-evaluation-meta" :evaluation="row" :group-key="group.key" editing /></td>
            <td class="quick-actions"><el-button type="danger" link :disabled="saving" @click="removeRow(index)">删除</el-button><el-button v-if="row._existing" type="primary" link :disabled="saving" @click="emit('open-existing',row._existing)">已有档案</el-button><p v-if="row._error" role="alert" class="quick-error">{{row._error}}</p></td>
          </tr><tr v-if="!form.rows.length"><td :colspan="selectedFields.length+4">暂无记录，请新增一行。</td></tr></tbody>
        </table></div>
      </AppForm>
    </div>
    <template #footer><span class="quick-count">共 {{form.rows.length}} 行<span v-if="saving">，正在保存第 {{savingIndex}} 行</span></span><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!form.rows.length" @click="save">保存登记</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,nextTick,reactive,ref} from 'vue'
import {ElInput as GridInput,ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import TalentEvaluationMeta from './TalentEvaluationMeta.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {quickNameFields,quickContactFields,quickRegistrationPayload,newQuickRegistrationRow} from '@/utils/talentQuickRegister'
import {handleTableArrowNavigation} from '@/utils/tableArrowNavigation'
import {resolveIdempotencyKey} from '@/utils/idempotency'
const props=defineProps({create:{type:Function,required:true}})
const emit=defineEmits(['saved','open-existing'])
const visible=ref(false),saving=ref(false),formRef=ref(),bodyRef=ref(),addCount=ref(5),savingIndex=ref(0)
const form=reactive({nameKinds:['chineseName'],contactKinds:['wechat'],rows:[]})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,locateDialogFieldByLabel,clearFieldSearch}=useDialogFieldSearch(bodyRef)
const selectedFields=computed(()=>[...quickNameFields.filter(field=>form.nameKinds.includes(field.key)),...quickContactFields.filter(field=>form.contactKinds.includes(field.key))])
const selectionRules=[{type:'array',required:true,min:1,max:2,message:'请选择1～2种',trigger:'change'}]
const fieldRules=field=>[{required:true,whitespace:true,message:`请填写${field.label}`,trigger:'blur'},...(['primaryEmail','secondaryEmail'].includes(field.key)?[{type:'email',message:'请输入有效邮箱',trigger:'blur'}]:[])]
const levels=[{value:'high',label:'高'},{value:'medium',label:'中'},{value:'low',label:'低'}]
const evaluationGroups=[{key:'punctuality',label:'守时度'},{key:'cooperation',label:'配合度'}]
async function open(){
  if(saving.value)return
  Object.assign(form,{nameKinds:['chineseName'],contactKinds:['wechat'],rows:[newQuickRegistrationRow()]})
  addCount.value=5;savingIndex.value=0;clearFieldSearch();visible.value=true;await nextTick();formRef.value?.clearValidate()
}
function addRows(count){if(saving.value)return;const amount=Math.min(100-form.rows.length,Math.max(1,Math.floor(Number(count)||1)));form.rows.push(...Array.from({length:amount},newQuickRegistrationRow))}
async function removeRow(index){if(saving.value)return;form.rows.splice(index,1);await nextTick();formRef.value?.clearValidate()}
function beforeClose(done){if(!saving.value)done()}
const createRow=(row,allowDuplicate=false)=>{
  const payload=quickRegistrationPayload({...row,nameKinds:form.nameKinds,contactKinds:form.contactKinds},allowDuplicate)
  const idempotencyKey=resolveIdempotencyKey(row._createState,payload)
  return props.create(payload,{idempotencyKey})
}
async function saveRow(row,index){
  try{return await createRow(row)}catch(error){
    const detail=error.rawDetail
    if(detail?.code!=='duplicate_talent')throw error
    row._existing=detail.duplicates?.[0]||null
    try{await ElMessageBox.confirm(`第${index+1}行发现联系方式相同的人才“${row._existing?.fullName||row._existing?.full_name||'未知'}”。仍然新建，还是保留本行核对？`,'疑似重复人才',{confirmButtonText:'仍然新建',cancelButtonText:'保留本行',distinguishCancelAndClose:true,type:'warning'})}
    catch{throw new Error('发现疑似重复人才，本行已保留，可打开已有档案核对')}
    return await createRow(row,true)
  }
}
async function save(){
  if(saving.value||!form.rows.length)return
  saving.value=true
  const savedKeys=new Set(),saved=[]
  let valid=false
  try{
    valid=await formRef.value.validate().catch(()=>false)
    if(!valid)return
    for(const [index,row] of form.rows.entries()){
      savingIndex.value=index+1;row._error='';row._existing=null
      try{saved.push(await saveRow(row,index));savedKeys.add(row._key)}catch(error){row._error=typeof error.detail==='string'?error.detail:error.message||'登记失败，请修改后重试'}
    }
    form.rows=form.rows.filter(row=>!savedKeys.has(row._key))
    if(saved.length)emit('saved',saved)
    if(!form.rows.length){visible.value=false;ElMessage.success(`已登记${saved.length}位人才`)}
    else ElMessage.warning(`成功${saved.length}行，失败${form.rows.length}行，失败行已保留`)
  }finally{
    saving.value=false;savingIndex.value=0;await nextTick()
    if(!valid)await formRef.value?.locateFirstError()
    else if(form.rows.length&&selectedFields.value.length)await locateDialogFieldByLabel(selectedFields.value[0].label)
  }
}
defineExpose({open})
</script>
<style scoped>
.quick-type-selection{display:grid;grid-template-columns:1fr 1fr;gap:16px}.quick-row-toolbar,.quick-row-toolbar>div{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.quick-row-toolbar{justify-content:space-between;margin-bottom:12px;color:var(--el-text-color-secondary);font-size:12px}.quick-row-toolbar .el-input-number{width:100px}.quick-row-toolbar .el-button+.el-button{margin-left:0}.quick-grid-scroll{overflow-x:auto;border:1px solid var(--el-border-color);border-radius:6px}.quick-grid{width:100%;min-width:900px;border-collapse:collapse;table-layout:fixed}.quick-grid th,.quick-grid td{border:1px solid var(--el-border-color);padding:8px;vertical-align:top}.quick-grid th{background:var(--el-fill-color-light);font-weight:500;text-align:left}.quick-grid .quick-index{width:65px;font-size:12px}.quick-field{width:200px}.quick-rating{width:230px}.quick-grid .quick-actions{width:160px}.quick-grid :deep(.el-form-item){margin-bottom:0}.quick-grid :deep(.el-form-item__label){position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.quick-grid :deep(.el-form-item__error){position:static}.quick-grid :deep(.el-select){width:100%}.quick-error{color:var(--el-color-danger);white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;margin:5px 0}.quick-row-error td{box-shadow:inset 0 2px var(--el-color-danger-light-7)}.quick-count{margin-right:auto;font-size:13px;color:var(--el-text-color-secondary)}.quick-evaluation-meta{gap:3px;margin:6px 0 0}.quick-evaluation-meta :deep(label){flex-direction:row;align-items:center;width:100%!important;font-size:11px;gap:5px}.quick-evaluation-meta :deep(label>.readonly-field){flex:1;min-width:0}.quick-evaluation-meta :deep(.el-input__wrapper){min-height:23px;padding:0 5px}.quick-evaluation-meta :deep(.el-input__inner){height:23px;font-size:11px}@media(max-width:600px){.quick-type-selection{grid-template-columns:1fr;gap:0}}
</style>
<style>
.el-dialog.talent-quick-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.talent-quick-dialog>.el-dialog__header{flex-shrink:0}.talent-quick-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.talent-quick-dialog>.el-dialog__footer{display:flex;align-items:center;gap:8px;flex-shrink:0;border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
</style>
