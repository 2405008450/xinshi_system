<template>
  <div class="annotation-workflow-page">
    <el-card class="workflow-card compact-list-card">
      <template #header>
        <div class="card-header">
          <div><h2>标注流程</h2><p>默认展示全部项目的进行状态；选择项目后仅查看该项目</p></div>
          <div class="header-actions">
            <CustomFieldManager v-if="projectId" table-code="assignment" :project-id="projectId" @changed="loadFields" />
            <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
            <el-button v-if="canWrite && !deleteMode" type="primary" @click="openEditor()">新增安排</el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-select v-model="projectId" clearable filterable placeholder="全部标注项目" style="width:340px" @change="handleProjectChange">
          <el-option v-for="item in projects" :key="item.id" :label="`${item.orderNo || '-'} · ${item.projectName || '未命名'}`" :value="item.id" />
        </el-select>
        <el-input v-model="keyword" clearable placeholder="搜索项目、人员编号或姓名" style="width:260px" @input="handleKeyword" @keyup.enter="loadRows" />
        <el-select v-model="roleFilter" clearable placeholder="人员角色" style="width:140px" @change="loadRows">
          <el-option v-for="(label,value) in roleLabels" :key="value" :label="label" :value="value" />
        </el-select>
        <el-select v-model="statusFilter" clearable placeholder="进行状态" style="width:140px" @change="loadRows"><el-option v-for="(label,value) in assignmentStatusLabels" :key="value" :label="label" :value="value" /></el-select>
        <el-button type="primary" @click="loadRows">查询</el-button><el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table ref="workflowTableRef" :data="rows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange">
        <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
        <el-table-column type="index" label="序号" width="70" align="center" />
        <el-table-column prop="projectOrderNo" label="订单号" width="130" />
        <el-table-column prop="projectName" label="项目名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="clientShortName" label="客户简称" width="120"><template #default="{row}">{{ row.clientShortName||'-' }}</template></el-table-column>
        <el-table-column label="角色" width="100"><template #default="{row}"><el-tag :type="row.assignmentRole==='quality_inspector'?'warning':'primary'" size="small">{{ roleLabels[row.assignmentRole] }}</el-tag></template></el-table-column>
        <el-table-column prop="resourceCode" label="人员编号" width="140"><template #default="{row}">{{ row.resourceCode || '-' }}</template></el-table-column>
        <el-table-column prop="personName" label="姓名" min-width="130" />
        <el-table-column min-width="160">
          <template #header><el-popover v-model:visible="languageFilterVisible" trigger="click" placement="bottom" :width="300"><template #reference><el-button link type="primary" class="language-filter-button">语种<span v-if="languageItemId">（已筛选）</span><el-icon><Filter /></el-icon></el-button></template><div class="language-filter-panel"><strong>按语种筛选</strong><el-select v-model="languageItemId" clearable filterable :disabled="!projectId" :placeholder="projectId?'全部语种':'请先选择项目'" style="width:100%" @change="loadRows"><el-option v-for="item in filterLanguageItems" :key="item.id" :label="item.display" :value="item.id" /></el-select><el-button link type="primary" @click="clearLanguageFilter">清除筛选</el-button></div></el-popover></template>
          <template #default="{row}">{{ row.languageDisplay || '-' }}</template>
        </el-table-column>
        <el-table-column label="人员价格" min-width="170"><template #default="{row}">{{ priceText(row.amount,row.unit,row.currency) }}</template></el-table-column>
        <el-table-column label="进行状态" width="100"><template #default="{row}"><el-tag :type="assignmentStatusType(row.assignmentStatus)" size="small">{{ assignmentStatusLabels[row.assignmentStatus]||'-' }}</el-tag></template></el-table-column>
        <el-table-column v-for="field in customFields" :key="field.id" :label="field.fieldLabel" min-width="130" show-overflow-tooltip><template #default="{row}">{{ customText(row.customValues?.[field.id]) }}</template></el-table-column>
        <el-table-column label="详情" width="90" fixed="right"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760" title="正式标注安排详情"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="detail"><el-descriptions :column="2" border size="small"><el-descriptions-item label="订单号">{{ row.projectOrderNo||'-' }}</el-descriptions-item><el-descriptions-item label="项目名称">{{ row.projectName||'-' }}</el-descriptions-item><el-descriptions-item label="客户简称">{{ row.clientShortName||'-' }}</el-descriptions-item><el-descriptions-item label="角色">{{ roleLabels[row.assignmentRole] }}</el-descriptions-item><el-descriptions-item label="人员">{{ row.personName }}（{{ row.resourceCode||'-' }}）</el-descriptions-item><el-descriptions-item label="进行状态">{{ assignmentStatusLabels[row.assignmentStatus]||'-' }}</el-descriptions-item><el-descriptions-item label="语种">{{ row.languageDisplay||'-' }}</el-descriptions-item><el-descriptions-item label="音频长度">{{ amountText(row.audioDurationValue,row.audioDurationUnit,durationUnitLabels) }}</el-descriptions-item><el-descriptions-item label="人员价格" :span="2">{{ priceText(row.amount,row.unit,row.currency) }}</el-descriptions-item><el-descriptions-item label="质量评分">{{ row.qualityScore||'-' }}</el-descriptions-item><el-descriptions-item label="评价备注" :span="2">{{ row.evaluationNote||'-' }}</el-descriptions-item><el-descriptions-item v-for="field in customFields" :key="field.id" :label="field.fieldLabel" :span="2">{{ customText(row.customValues?.[field.id]) }}</el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
        <el-table-column v-if="!deleteMode" label="操作" width="90" fixed="right" align="center"><template #default="{row}"><el-button v-if="canWrite" link type="primary" @click="openEditor(row)">编辑</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!loading&&!rows.length" :description="projectId?'该项目暂无正式标注安排':'暂无正式标注安排'" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="form.id?'编辑正式安排':'新增正式安排'" width="min(760px,calc(100vw - 32px))" top="5vh" class="workflow-dialog">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="标注项目" prop="projectId"><el-select v-model="form.projectId" filterable :disabled="Boolean(form.id)" placeholder="请选择归属项目" style="width:100%" @change="editorProjectChanged"><el-option v-for="item in projects" :key="item.id" :label="`${item.orderNo || '-'} · ${item.projectName || '未命名'}`" :value="item.id" /></el-select></el-form-item>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12"><el-form-item label="人员角色" prop="assignmentRole"><el-select v-model="form.assignmentRole" style="width:100%"><el-option v-for="(label,value) in roleLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="12"><el-form-item label="人员" prop="personId"><el-select v-model="form.personId" filterable style="width:100%"><el-option v-for="item in talents" :key="item.id" :label="`${item.resourceCode||'-'} · ${item.fullName}`" :value="item.id" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item label="语种"><el-select v-model="form.languageItemId" clearable filterable style="width:100%"><el-option v-for="item in languageItems" :key="item.id" :label="item.display" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="音频长度"><div class="amount-input"><el-input-number v-model="form.audioDurationValue" :min="0" :precision="3" /><el-select v-model="form.audioDurationUnit" clearable placeholder="单位"><el-option v-for="(label,value) in durationUnitLabels" :key="value" :label="label" :value="value" /></el-select></div></el-form-item>
        <el-form-item label="人员价格"><div class="amount-input"><el-input-number v-model="form.amount" :min="0" :precision="6" /><el-select v-model="form.unit" clearable placeholder="单位"><el-option v-for="(label,value) in priceUnitLabels" :key="value" :label="label" :value="value" /></el-select><el-select v-model="form.currency" style="width:100px"><el-option label="CNY" value="CNY" /><el-option label="USD" value="USD" /><el-option label="EUR" value="EUR" /></el-select></div></el-form-item>
        <el-form-item label="进行状态"><el-select v-model="form.assignmentStatus" style="width:100%"><el-option v-for="(label,value) in assignmentStatusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="质量评分"><el-input v-model="form.qualityScore" /></el-form-item>
        <el-form-item label="评价备注"><el-input v-model="form.evaluationNote" type="textarea" :rows="3" /></el-form-item>
        <AnnotationCustomFieldInputs :fields="editorFields" :values="form.customValues" />
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveRow">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed,onBeforeUnmount,onMounted,reactive,ref } from 'vue'
import { Filter } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as annotationApi from '@/api/annotationProjects'
import * as opsApi from '@/api/annotationOps'
import { getProjectTalentOptions } from '@/api/talents'
import { hasPermission } from '@/utils/permission'
import CustomFieldManager from '@/components/annotation/CustomFieldManager.vue'
import AnnotationCustomFieldInputs from '@/components/annotation/AnnotationCustomFieldInputs.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'

const projects=ref([]),talents=ref([]),rows=ref([]),customFields=ref([]),editorFields=ref([]),projectId=ref(''),languageItemId=ref(''),roleFilter=ref(''),statusFilter=ref(''),keyword=ref(''),loading=ref(false),dialogVisible=ref(false),saving=ref(false),languageFilterVisible=ref(false),formRef=ref(),workflowTableRef=ref(null)
let keywordTimer,requestController,requestId=0
const roleLabels={annotator:'标注员',quality_inspector:'质检员'},durationUnitLabels={second:'秒',minute:'分钟',hour:'小时'},priceUnitLabels={item:'条',second:'秒',minute:'分钟',hour:'小时'}
const assignmentStatusLabels={assigned:'已安排',in_progress:'进行中',completed:'已完成',cancelled:'已取消'}
const canWrite=computed(()=>hasPermission('projects:write'))
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef:workflowTableRef,deleteRow:(row)=>opsApi.deleteAnnotationWorkflow(row.projectId,row.id),getLabel:(row)=>`${row.personName || '未命名人员'}的${roleLabels[row.assignmentRole] || '标注'}安排`,reload:()=>loadRows(),entityName:'标注流程记录'})
const filterProject=computed(()=>projects.value.find(item=>item.id===projectId.value))
const editorProject=computed(()=>projects.value.find(item=>item.id===form.projectId))
const languageItems=computed(()=>editorProject.value?.languageItems||[])
const filterLanguageItems=computed(()=>filterProject.value?.languageItems||[])
const emptyForm=()=>({id:'',projectId:'',personId:'',assignmentRole:'annotator',languageItemId:null,audioDurationValue:null,audioDurationUnit:null,amount:null,unit:null,currency:'CNY',customValues:{},assignmentStatus:'assigned',qualityScore:'',evaluationNote:''})
const form=reactive(emptyForm())
const rules={projectId:[{required:true,message:'请选择标注项目',trigger:'change'}],personId:[{required:true,message:'请选择人员',trigger:'change'}],assignmentRole:[{required:true,message:'请选择人员角色',trigger:'change'}]}
const normalizePair=(amount,unit,label)=>{if((amount===null||amount===undefined)!==!unit)throw new Error(`${label}和单位必须同时填写`)}
const payload=()=>{normalizePair(form.audioDurationValue,form.audioDurationUnit,'音频长度');normalizePair(form.amount,form.unit,'人员价格');return{personId:form.personId,assignmentRole:form.assignmentRole,languageItemId:form.languageItemId||null,audioDurationValue:form.audioDurationValue,audioDurationUnit:form.audioDurationUnit||null,amount:form.amount,unit:form.unit||null,currency:form.currency||'CNY',customValues:form.customValues,assignmentStatus:form.assignmentStatus,qualityScore:form.qualityScore?.trim()||null,evaluationNote:form.evaluationNote?.trim()||null}}
const loadFields=async()=>{customFields.value=projectId.value?await opsApi.getCustomFields('assignment',projectId.value):[]}
const loadRows=async()=>{clearTimeout(keywordTimer);requestController?.abort();requestController=new AbortController();const current=++requestId;loading.value=true;try{const result=await opsApi.getAnnotationWorkflow(projectId.value,{language_item_id:languageItemId.value||undefined,keyword:keyword.value.trim()||undefined,assignment_role:roleFilter.value||undefined,assignment_status:statusFilter.value||undefined},{signal:requestController.signal});if(current===requestId)rows.value=result}catch(error){if(error.code!=='ERR_CANCELED')ElMessage.error(error.detail||'加载标注流程失败')}finally{if(current===requestId)loading.value=false}}
const handleProjectChange=async()=>{languageItemId.value='';await Promise.all([loadRows(),loadFields()])}
const handleKeyword=value=>{clearTimeout(keywordTimer);if(!value)return loadRows();keywordTimer=setTimeout(loadRows,400)}
const resetFilters=()=>{projectId.value='';keyword.value='';roleFilter.value='';statusFilter.value='';languageItemId.value='';languageFilterVisible.value=false;customFields.value=[];loadRows()}
const clearLanguageFilter=()=>{languageItemId.value='';languageFilterVisible.value=false;loadRows()}
const editorProjectChanged=async()=>{form.languageItemId=null;form.customValues={};editorFields.value=form.projectId?await opsApi.getCustomFields('assignment',form.projectId):[]}
const openEditor=async(row=null)=>{Object.assign(form,emptyForm(),row?{...row,projectId:row.projectId,customValues:{...(row.customValues||{})}}:{projectId:projectId.value});editorFields.value=form.projectId?await opsApi.getCustomFields('assignment',form.projectId):[];dialogVisible.value=true}
const saveRow=async()=>{if(!await formRef.value?.validate().catch(()=>false))return;saving.value=true;try{const data=payload();form.id?await opsApi.updateAnnotationWorkflow(form.projectId,form.id,data):await opsApi.createAnnotationWorkflow(form.projectId,data);dialogVisible.value=false;ElMessage.success('正式安排已保存');await loadRows()}catch(error){ElMessage.error(error.detail||error.message||'保存失败')}finally{saving.value=false}}
const amountText=(amount,unit,labels)=>amount===null||amount===undefined?'-':`${amount} ${labels[unit]||unit||''}`
const priceText=(amount,unit,currency)=>amount===null||amount===undefined?'-':`${amount} ${currency||'CNY'} / ${priceUnitLabels[unit]||unit||'-'}`
const customText=value=>Array.isArray(value)?value.join('、'):value===true?'是':value===false?'否':value??'-'
const assignmentStatusType=value=>({assigned:'info',in_progress:'primary',completed:'success',cancelled:'danger'}[value]||'info')
onMounted(async()=>{try{const [projectRows,talentRows]=await Promise.all([annotationApi.getAnnotationProjects({skip:0,limit:500}),getProjectTalentOptions('annotation')]);projects.value=projectRows;talents.value=talentRows;await loadRows()}catch(error){ElMessage.error(error.detail||'加载标注流程基础数据失败')}})
onBeforeUnmount(()=>{clearTimeout(keywordTimer);requestController?.abort()})
</script>

<style scoped>
.card-header,.header-actions,.filters,.amount-input{display:flex;align-items:center}.card-header{justify-content:space-between}.card-header h2{margin:0}.card-header p{margin:4px 0 0;color:var(--el-text-color-secondary)}.header-actions,.filters{gap:8px}.filters{margin-bottom:16px;flex-wrap:wrap}.language-filter-button{font-weight:600}.language-filter-panel{display:flex;flex-direction:column;gap:12px}.amount-input{width:100%;gap:8px}.amount-input .el-input-number{flex:1}.amount-input .el-select{width:105px;flex:none}.detail{max-height:560px;overflow-y:auto;word-break:break-word}
</style>
<style>
.workflow-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.workflow-dialog .el-dialog__header,.workflow-dialog .el-dialog__footer{flex:0 0 auto}.workflow-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.workflow-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light)}
</style>
