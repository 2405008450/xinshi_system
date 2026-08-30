<template>
  <el-card class="compact-list-card"><template #header><div class="card-header"><div><h2>试标流程</h2><p>默认展示全部项目的试标进度；选择项目后仅查看该项目</p></div><div class="header-actions"><CustomFieldManager v-if="canWrite && projectId" table-code="trial" :project-id="projectId" @changed="loadFields" /><BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" /><el-button v-if="canWrite && !deleteMode" type="primary" @click="openEditor()">新增试标</el-button></div></div></template>
    <div class="filters"><el-select v-model="projectId" clearable filterable placeholder="全部标注项目" style="width:min(420px, calc(100vw - 32px))" @change="changeProject"><el-option v-for="item in projects" :key="item.id" :label="`${item.orderNo || '-'} · ${item.projectName || '未命名'}`" :value="item.id" /></el-select><el-input v-model="keyword" clearable placeholder="搜索项目、编号、姓名、意愿或评语" style="width:300px" @input="onInput" @keyup.enter="search" /><el-select v-model="statusFilter" clearable placeholder="试标状态" @change="search"><el-option v-for="(label,value) in statusLabels" :key="value" :label="label" :value="value" /></el-select><el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button></div>
    <el-table ref="trialTableRef" :data="displayRows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange"><el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" /><el-table-column type="index" label="序号" width="65" /><el-table-column prop="projectOrderNo" label="订单号" width="130" /><el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip /><el-table-column prop="clientShortName" label="客户简称" width="120"><template #default="{row}">{{ row.clientShortName||'-' }}</template></el-table-column><el-table-column prop="resourceCode" label="标注员编号" width="120" /><el-table-column prop="personName" label="姓名" width="120" /><el-table-column prop="roundNo" label="轮次" width="75" /><el-table-column label="平台账号" min-width="190" show-overflow-tooltip><template #default="{row}">{{ trialAccountLabel(row) }}</template></el-table-column><el-table-column prop="willingnessText" label="意愿" min-width="150" show-overflow-tooltip /><el-table-column label="状态" width="100"><template #default="{row}"><el-tag :type="statusType(row.trialStatus)" size="small">{{ statusLabels[row.trialStatus] }}</el-tag></template></el-table-column><el-table-column label="结果" width="110"><template #default="{row}">{{ resultLabels[row.trialResult]||'-' }}</template></el-table-column>
      <el-table-column v-for="field in customFields" :key="field.id" :label="field.fieldLabel" min-width="120"><template #default="{row}">{{ customText(row.customValues?.[field.id]) }}</template></el-table-column>
      <el-table-column label="详情" width="90" fixed="right" align="center"><template #default="{row}"><BusinessDetailPopover :row="row" title="试标记录详情"><template #content><el-descriptions :column="2" border size="small"><el-descriptions-item label="订单号">{{ row.projectOrderNo||'-' }}</el-descriptions-item><el-descriptions-item label="项目名称">{{ row.projectName||'-' }}</el-descriptions-item><el-descriptions-item label="客户简称">{{ row.clientShortName||'-' }}</el-descriptions-item><el-descriptions-item label="标注员">{{ row.personName||'-' }}（{{ row.resourceCode||'-' }}）</el-descriptions-item><el-descriptions-item label="轮次">第 {{ row.roundNo }} 轮</el-descriptions-item><el-descriptions-item label="平台账号">{{ trialAccountLabel(row) }}</el-descriptions-item><el-descriptions-item label="状态">{{ statusLabels[row.trialStatus]||'-' }}</el-descriptions-item><el-descriptions-item label="意愿" :span="2">{{ row.willingnessText||'-' }}</el-descriptions-item><el-descriptions-item label="结果">{{ resultLabels[row.trialResult]||'-' }}</el-descriptions-item><el-descriptions-item label="评语" :span="2">{{ row.resultNote||'-' }}</el-descriptions-item><el-descriptions-item v-for="field in customFields" :key="field.id" :label="field.fieldLabel" :span="field.dataType==='textarea'?2:1">{{ customText(row.customValues?.[field.id]) }}</el-descriptions-item></el-descriptions></template></BusinessDetailPopover></template></el-table-column>
      <el-table-column v-if="canWrite && !deleteMode" label="操作" width="120" fixed="right" align="center"><template #default="{row}"><PrimaryEditButton @click="openEditor(row)" /></template></el-table-column></el-table>
  </el-card>
  <el-dialog v-model="dialogVisible" :title="form.id?'编辑试标记录':'新增试标记录'" width="min(760px,calc(100vw - 32px))" top="5vh" class="trial-dialog">
    <el-form label-width="90px">
      <el-form-item label="标注项目" required><el-select v-model="form.projectId" filterable :disabled="Boolean(form.id)" placeholder="请选择归属项目" style="width:100%" @change="editorProjectChanged"><el-option v-for="item in projects" :key="item.id" :label="`${item.orderNo || '-'} · ${item.projectName || '未命名'}`" :value="item.id" /></el-select></el-form-item>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="标注员" required><el-select v-model="form.personId" filterable :disabled="!form.projectId" placeholder="请先选择项目；人员按项目语种过滤" style="width:100%" @change="personChanged"><el-option v-for="item in eligibleTalents" :key="item.id" :label="`${item.fullName}（${item.resourceCode||'-'}）`" :value="item.id" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="轮次"><el-input-number v-model="form.roundNo" :min="1" style="width:100%" /></el-form-item></el-col>
      </el-row>
      <el-form-item label="平台账号"><el-select v-model="form.platformAccountId" clearable filterable :loading="accountLoading" :disabled="!form.projectId||!form.personId" placeholder="可选；来源于“标注员账号”中该项目的当前绑定账号" no-data-text="该标注员在此项目下暂无绑定账号" style="width:100%"><el-option v-for="item in accountOptions" :key="item.id" :label="accountOptionLabel(item)" :value="item.id" /></el-select></el-form-item>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="试标状态"><el-select v-model="form.trialStatus" style="width:100%"><el-option v-for="(label,value) in statusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="试标结果"><el-select v-model="form.trialResult" clearable style="width:100%"><el-option v-for="(label,value) in resultLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
      </el-row>
      <el-form-item label="人工意愿"><el-input v-model="form.willingnessText" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="结果评语"><el-input v-model="form.resultNote" type="textarea" :rows="4" /></el-form-item>
      <AnnotationCustomFieldInputs :fields="editorFields" :values="form.customValues" />
    </el-form>
    <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as projectApi from '@/api/annotationProjects'
import * as ops from '@/api/annotationOps'
import * as talentApi from '@/api/talents'
import CustomFieldManager from '@/components/annotation/CustomFieldManager.vue'
import AnnotationCustomFieldInputs from '@/components/annotation/AnnotationCustomFieldInputs.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { hasPermission } from '@/utils/permission'
const projects=ref([]),talents=ref([]),rows=ref([]),customFields=ref([]),editorFields=ref([]),accountOptions=ref([]),projectId=ref(''),keyword=ref(''),statusFilter=ref(''),loading=ref(false),accountLoading=ref(false),dialogVisible=ref(false),saving=ref(false),trialTableRef=ref(null)
const canWrite=hasPermission('projects:write')
const form=reactive({id:'',projectId:'',personId:'',platformAccountId:null,roundNo:1,willingnessText:'',trialStatus:'pending',trialResult:null,resultNote:'',customValues:{}})
const statusLabels={pending:'待开始',in_progress:'进行中',submitted:'已提交',reviewing:'评审中',completed:'已完成',cancelled:'已取消'}
const resultLabels={passed:'通过',failed:'未通过',partially_passed:'部分通过',withdrawn:'已退出'}
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:trialTableRef,deleteRow:(row)=>ops.deleteTrial(row.id),getLabel:(row)=>`${row.personName || '未命名标注员'}第 ${row.roundNo} 轮试标`,reload:()=>search(),entityName:'试标记录'})
let timer,controller,requestId=0,accountRequestId=0
const displayRows=computed(()=>rows.value)
const selectedEditorProject=computed(()=>projects.value.find(item=>item.id===form.projectId))
const languageSkillKey=item=>`${item.sourceLanguageId||''}:${item.targetLanguageId||''}`
const eligibleTalents=computed(()=>{
  const project=selectedEditorProject.value
  if(!project)return[]
  const projectLanguages=new Set((project.languageItems||[]).map(languageSkillKey))
  if(!projectLanguages.size)return talents.value
  return talents.value.filter(item=>{
    if(form.id&&item.id===form.personId)return true
    return (item.annotationLanguageSkills||[]).some(skill=>projectLanguages.has(languageSkillKey(skill)))
  })
})
const statusType=(value)=>({pending:'info',in_progress:'primary',submitted:'warning',reviewing:'warning',completed:'success',cancelled:'danger'}[value]||'info')
const customText=(value)=>Array.isArray(value)?value.join('、')||'-':value===null||value===undefined||value===''?'-':value
const accountOptionLabel=item=>[item.platformName||item.platformUrl,item.nickname,item.loginAccount].filter(Boolean).join(' · ')||'未命名账号'
const trialAccountLabel=row=>[row.platformName,row.platformAccountNickname].filter(Boolean).join(' · ')||'-'
const loadFields=async()=>{customFields.value=projectId.value?await ops.getCustomFields('trial',projectId.value):[]}
const loadAccounts=async(projectIdValue=form.projectId,personIdValue=form.personId)=>{
  const current=++accountRequestId
  accountOptions.value=[]
  if(!projectIdValue||!personIdValue)return
  accountLoading.value=true
  try{
    const result=await ops.getAccounts({projectId:projectIdValue,personId:personIdValue,assignmentState:'assigned',skip:0,limit:500})
    if(current===accountRequestId)accountOptions.value=result
  }catch(error){
    if(current===accountRequestId)ElMessage.error(error.detail||'加载标注员平台账号失败')
  }finally{
    if(current===accountRequestId)accountLoading.value=false
  }
}
const search=async()=>{clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++requestId;loading.value=true;try{const result=await ops.getTrials(projectId.value,{skip:0,limit:500,keyword:keyword.value.trim()||undefined,trial_status:statusFilter.value||undefined},{signal:controller.signal});if(current===requestId)rows.value=result;await loadFields()}catch(error){if(error.code!=='ERR_CANCELED')ElMessage.error(error.detail||'加载试标记录失败')}finally{if(current===requestId)loading.value=false}}
const onInput=(value)=>{clearTimeout(timer);if(!value)return search();timer=setTimeout(search,400)}
const changeProject=async()=>{await search()}
const editorProjectChanged=async()=>{form.personId='';form.platformAccountId=null;accountOptions.value=[];form.customValues={};await (form.projectId?ops.getCustomFields('trial',form.projectId).then(result=>{editorFields.value=result}):Promise.resolve(editorFields.value=[]))}
const personChanged=async()=>{form.platformAccountId=null;await loadAccounts()}
const reset=()=>{projectId.value='';keyword.value='';statusFilter.value='';customFields.value=[];search()}
const openEditor=async(row=null)=>{Object.assign(form,{id:'',projectId:projectId.value,personId:'',platformAccountId:null,roundNo:1,willingnessText:'',trialStatus:'pending',trialResult:null,resultNote:'',customValues:{}},row||{});dialogVisible.value=true;await Promise.all([loadAccounts(),form.projectId?ops.getCustomFields('trial',form.projectId).then(result=>{editorFields.value=result}):Promise.resolve(editorFields.value=[])])}
const save=async()=>{if(!form.projectId)return ElMessage.warning('请选择标注项目');if(!form.personId)return ElMessage.warning('请选择标注员');saving.value=true;try{form.id?await ops.updateTrial(form.id,form):await ops.createTrial(form);dialogVisible.value=false;ElMessage.success('试标记录已保存');await search()}catch(error){ElMessage.error(error.detail||'保存失败')}finally{saving.value=false}}
onMounted(async()=>{const [ps,ts]=await Promise.all([projectApi.getAnnotationProjects({skip:0,limit:500}),talentApi.getProjectTalentOptions('annotation')]);projects.value=ps;talents.value=ts;await search()})
onBeforeUnmount(()=>{clearTimeout(timer);controller?.abort()})
</script>
<style scoped>.card-header,.header-actions,.filters{display:flex;align-items:center}.card-header{justify-content:space-between}.card-header h2{margin:0}.card-header p{margin:4px 0 0;color:var(--el-text-color-secondary)}.header-actions,.filters{gap:8px}.filters{margin-bottom:16px;flex-wrap:wrap}.detail{max-height:560px;overflow:auto}</style>
<style>.trial-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.trial-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.trial-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}</style>
