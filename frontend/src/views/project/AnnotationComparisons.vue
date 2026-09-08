<template>
  <el-card class="comparison-card compact-list-card">
    <template #header>
      <div class="comparison-header">
        <div>
          <strong>项目对比</strong>
          <span class="comparison-header__hint">将相似或有关联的标注项目放在同一组中横向比较</span>
        </div>
        <div class="comparison-header__actions">
          <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
          <el-button v-if="canWrite && !deleteMode" type="primary" @click="openCreate">新增比较组</el-button>
        </div>
      </div>
    </template>

    <AppForm :inline="true" class="comparison-search" @submit.prevent>
      <el-form-item label="关键字">
        <el-input v-model="keyword" clearable placeholder="比较组名称或比较说明" @input="handleKeywordInput" @keyup.enter="search" />
      </el-form-item>
      <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="resetSearch">重置</el-button></el-form-item>
    </AppForm>

    <el-table ref="tableRef" v-loading="loading" :data="rows" row-key="id" border @expand-change="handleExpand" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
      <el-table-column type="expand" width="48" fixed="left">
        <template #default="{ row }">
          <div class="comparison-expanded" v-loading="detailLoadingIds.has(row.id)">
            <div class="comparison-description"><span>比较说明</span><p>{{ row.description }}</p></div>
            <el-alert v-if="row.memberCount < 2" :title="row.memberCount ? '当前仅剩一个项目，请编辑比较组补充项目' : '组内项目均已删除，请编辑比较组补充项目'" type="warning" :closable="false" show-icon />
            <div v-if="details[row.id]?.projects?.length" class="comparison-matrix-wrap">
              <table class="comparison-matrix">
                <thead><tr><th class="comparison-matrix__field">对比字段</th><th v-for="project in details[row.id].projects" :key="project.projectId">
                  <AnnotationProjectDetailPopover :project-id="project.projectId" :summary="project"><template #reference><el-button type="primary" link class="comparison-project-link" @click.stop>{{ project.projectName || project.orderNo }}</el-button></template></AnnotationProjectDetailPopover>
                </th></tr></thead>
                <tbody><tr v-for="field in comparisonFields" :key="field.key"><th class="comparison-matrix__field">{{ field.label }}</th><td v-for="project in details[row.id].projects" :key="project.projectId"><el-tag v-if="field.key === 'projectStatus'" :type="statusType(project.projectStatus)" size="small">{{ statusLabel(project.projectStatus) }}</el-tag><span v-else>{{ fieldValue(project, field) }}</span></td></tr></tbody>
              </table>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="比较组名称" min-width="190" fixed="left">
        <template #default="{ row }">
          <el-popover trigger="hover" placement="right" :width="360">
            <template #reference><el-button type="primary" link class="comparison-group-link" @click.stop="toggleGroup(row)">{{ row.name }}</el-button></template>
            <div class="member-preview"><strong>组内项目（{{ row.memberCount }}）</strong><div v-if="row.members.length"><div v-for="item in row.members" :key="item.projectId">{{ item.orderNo }} · {{ item.projectName || '未命名项目' }}</div></div><span v-else>组内项目均已删除</span></div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" width="165"><template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template></el-table-column>
      <el-table-column prop="description" label="比较说明" min-width="320" show-overflow-tooltip />
      <el-table-column prop="memberCount" label="项目数" width="90" align="center" />
      <el-table-column v-if="!deleteMode" label="操作" width="90" fixed="right"><template #default="{ row }"><el-button v-if="canWrite" type="primary" link @click="openEdit(row)">编辑</el-button></template></el-table-column>
    </el-table>

    <div class="comparison-pagination"><el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next, jumper" @current-change="fetchGroups" @size-change="handlePageSize" /></div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑项目比较组' : '新增项目比较组'" width="min(760px, calc(100vw - 32px))" top="5vh" class="comparison-dialog" append-to-body @closed="resetForm">
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="比较组名称" prop="name"><el-input v-model="form.name" maxlength="150" show-word-limit placeholder="请输入有业务含义的比较组名称" /></el-form-item>
        <el-form-item label="比较说明" prop="description"><el-input v-model="form.description" type="textarea" :rows="5" maxlength="5000" show-word-limit placeholder="请说明比较目的、项目之间的联系或讨论结论" /></el-form-item>
        <el-form-item label="比较项目" prop="projectIds">
          <el-select v-model="form.projectIds" multiple filterable remote reserve-keyword :remote-method="searchProjects" :loading="projectLoading" value-key="id" placeholder="按订单号或项目名称搜索，选择 2～10 个项目" style="width:100%" @change="syncSelectedOptions">
            <el-option v-for="item in mergedProjectOptions" :key="item.id" :label="projectOptionLabel(item)" :value="item.id" />
          </el-select>
          <div class="project-selection-hint">已选择 {{ form.projectIds.length }} 个；选择顺序即横向对比顺序。</div>
        </el-form-item>
      </AppForm>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="submitting" @click="submit">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as comparisonApi from '@/api/annotationComparisons'
import * as annotationApi from '@/api/annotationProjects'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
import AppForm from '@/components/common/AppForm.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { hasPermission } from '@/utils/permission'

const canWrite = hasPermission('projects:write')
const rows=ref([]), loading=ref(false), keyword=ref(''), tableRef=ref(), details=reactive({}), detailLoadingIds=ref(new Set())
const pagination=reactive({page:1,limit:20,total:0})
let listController, listRequestId=0, searchTimer, projectTimer, projectController, projectRequestId=0
const setDetailLoading=(id,value)=>{const next=new Set(detailLoadingIds.value);value?next.add(id):next.delete(id);detailLoadingIds.value=next}
const fetchGroups=async()=>{listController?.abort();listController=new AbortController();const current=++listRequestId;loading.value=true;try{const page=await comparisonApi.getComparisonGroupPage({skip:(pagination.page-1)*pagination.limit,limit:pagination.limit,keyword:keyword.value.trim()||undefined},{signal:listController.signal});if(current!==listRequestId)return;rows.value=page?.items||[];pagination.total=page?.total||0}catch(error){if(current!==listRequestId||error?.code==='ERR_CANCELED')return;ElMessage.error(error.detail||'项目比较组加载失败')}finally{if(current===listRequestId)loading.value=false}}
const search=()=>{exitDeleteMode();clearTimeout(searchTimer);pagination.page=1;fetchGroups()}
const handleKeywordInput=(value)=>{clearTimeout(searchTimer);if(!value?.trim())return search();searchTimer=setTimeout(search,400)}
const resetSearch=()=>{keyword.value='';search()}
const handlePageSize=()=>{pagination.page=1;fetchGroups()}
const loadDetail=async(row)=>{setDetailLoading(row.id,true);try{details[row.id]=await comparisonApi.getComparisonGroup(row.id)}catch(error){ElMessage.error(error.detail||'比较详情加载失败')}finally{setDetailLoading(row.id,false)}}
const handleExpand=(row,expandedRows)=>{if((expandedRows||[]).some((item)=>item.id===row.id))loadDetail(row)}
const toggleGroup=(row)=>tableRef.value?.toggleRowExpansion(row)
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination,deleteRow:(row)=>comparisonApi.deleteComparisonGroup(row.id),getLabel:(row)=>row.name,reload:fetchGroups,onDeleted:(row)=>{delete details[row.id]},entityName:'项目比较组'})

const emptyForm=()=>({id:'',name:'',description:'',projectIds:[],updatedAt:'',originalProjectIds:[]})
const form=reactive(emptyForm()), formRef=ref(), dialogVisible=ref(false), submitting=ref(false), projectLoading=ref(false), remoteOptions=ref([]), selectedOptions=ref([])
const mergedProjectOptions=computed(()=>{const byId=new Map();[...selectedOptions.value,...remoteOptions.value].forEach((item)=>byId.set(item.id,item));return [...byId.values()]})
const projectOptionLabel=(item)=>`${item.orderNo||'-'} · ${item.projectName||'未命名项目'}`
const membershipChanged=()=>JSON.stringify(form.projectIds)!==JSON.stringify(form.originalProjectIds)
const validateProjects=(_rule,value,callback)=>{const count=value?.length||0;if(count>10)return callback(new Error('每个比较组最多选择 10 个项目'));if(count<2&&(!form.id||membershipChanged()))return callback(new Error('请至少选择 2 个项目'));if(new Set(value).size!==count)return callback(new Error('不能重复选择同一项目'));callback()}
const rules={name:[{validator:(_r,v,cb)=>String(v||'').trim()?cb():cb(new Error('请输入比较组名称')),trigger:['blur','change']}],description:[{validator:(_r,v,cb)=>String(v||'').trim()?cb():cb(new Error('请输入比较说明')),trigger:['blur','change']}],projectIds:[{validator:validateProjects,trigger:'change'}]}
const resetForm=()=>{Object.assign(form,emptyForm());remoteOptions.value=[];selectedOptions.value=[];formRef.value?.clearValidate()}
const searchProjects=(query='')=>{clearTimeout(projectTimer);projectTimer=setTimeout(()=>fetchProjectOptions(query),250)}
const fetchProjectOptions=async(query='')=>{projectController?.abort();projectController=new AbortController();const current=++projectRequestId;projectLoading.value=true;try{const page=await annotationApi.getAnnotationProjectPage({skip:0,limit:50,keyword:String(query||'').trim()||undefined},{signal:projectController.signal});if(current===projectRequestId)remoteOptions.value=page?.items||[]}catch(error){if(current!==projectRequestId||error?.code==='ERR_CANCELED')return;ElMessage.error(error.detail||'标注项目搜索失败')}finally{if(current===projectRequestId)projectLoading.value=false}}
const syncSelectedOptions=()=>{const byId=new Map(mergedProjectOptions.value.map((item)=>[item.id,item]));selectedOptions.value=form.projectIds.map((id)=>byId.get(id)).filter(Boolean)}
const openCreate=()=>{resetForm();dialogVisible.value=true;fetchProjectOptions()}
const openEdit=async(row)=>{try{const detail=await comparisonApi.getComparisonGroup(row.id);const projects=detail.projects||[];Object.assign(form,{id:detail.id,name:detail.name,description:detail.description,projectIds:projects.map((item)=>item.projectId),updatedAt:detail.updatedAt,originalProjectIds:projects.map((item)=>item.projectId)});selectedOptions.value=projects.map((item)=>({id:item.projectId,orderNo:item.orderNo,projectName:item.projectName}));dialogVisible.value=true;fetchProjectOptions()}catch(error){ElMessage.error(error.detail||'比较组详情加载失败')}}
const submit=async()=>{const valid=await formRef.value?.validate().catch(()=>false);if(!valid)return;submitting.value=true;try{const base={name:form.name.trim(),description:form.description.trim()};if(form.id){const payload={...base,expectedUpdatedAt:form.updatedAt};if(membershipChanged())payload.projectIds=form.projectIds;await comparisonApi.updateComparisonGroup(form.id,payload);ElMessage.success('项目比较组已更新')}else{await comparisonApi.createComparisonGroup({...base,projectIds:form.projectIds});ElMessage.success('项目比较组已创建')}dialogVisible.value=false;pagination.page=1;await fetchGroups()}catch(error){ElMessage.error(error.detail||'项目比较组保存失败')}finally{submitting.value=false}}

const projectTypeMap={audio_collection:'音频采集',audio_annotation:'音频标注',audio_evaluation:'音频评测',text_evaluation:'文本评测',text_annotation:'文本标注',quality_inspection:'质检',listening_test:'测听',slot_deduction:'扣槽',generalization:'泛化',translation:'翻译',ai_evaluation:'ai评测'}
const statusMap={initial_consultation:'初步咨询',consultation_no_result:'初步咨询后无结果',resource_sourcing:'资源开拓',resource_sourcing_cancelled:'取消资源开拓',trial_preparation:'试标准备',trial_in_progress:'试标中',trial_passed:'试标通过',trial_failed:'试标未通过',trial_partially_passed:'部分试标通过',project_in_progress:'项目进行中',sent_to_client:'已发客户',client_feedback:'客户反馈',cancelled:'已取消',partially_cancelled:'已部分取消',paused:'暂停',actively_abandoned:'主动放弃'}
const statusLabel=(value)=>statusMap[value]||value||'-'
const statusType=(value)=>({resource_sourcing:'primary',trial_preparation:'warning',trial_in_progress:'warning',trial_passed:'success',trial_failed:'danger',trial_partially_passed:'warning',project_in_progress:'primary',sent_to_client:'success',client_feedback:'warning',cancelled:'danger',partially_cancelled:'warning',paused:'warning',actively_abandoned:'danger'}[value]||'info')
const comparisonFields=[{key:'orderNo',label:'订单号'},{key:'client',label:'客户'},{key:'projectTypes',label:'项目类型'},{key:'languageItemsDisplay',label:'语言方向'},{key:'customerPriceSummary',label:'客户单价'},{key:'clientManagerName',label:'客户经理'},{key:'projectManagerName',label:'项目经理'},{key:'projectStatus',label:'项目进度'},{key:'potentialDemand',label:'（潜在）需求量'}]
const fieldValue=(project,field)=>{let value=project[field.key];if(field.key==='client')value=project.clientShortName||project.clientFullName;if(field.key==='projectTypes')value=(project.projectTypes||[]).map((item)=>projectTypeMap[item]||item).join('；');return value===null||value===undefined||value===''?'-':String(value)}
onMounted(fetchGroups)
onBeforeUnmount(()=>{clearTimeout(searchTimer);clearTimeout(projectTimer);listController?.abort();projectController?.abort()})
</script>

<style scoped>
.comparison-header,.comparison-header__actions,.comparison-search { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.comparison-header__hint { margin-left:12px; color:var(--el-text-color-secondary); font-size:13px; }
.comparison-search { justify-content:flex-start; margin-bottom:12px; }
.comparison-search :deep(.el-form-item) { margin-bottom:0; }
.comparison-search .el-input { width:min(420px, calc(100vw - 32px)); }
.comparison-pagination { display:flex; justify-content:flex-end; margin-top:16px; }
.comparison-group-link,.comparison-project-link { white-space:normal; text-align:left; }
.member-preview { display:grid; gap:8px; line-height:1.6; }
.comparison-expanded { padding:4px 12px 16px; display:grid; gap:12px; }
.comparison-description { display:grid; grid-template-columns:80px 1fr; gap:12px; padding:12px; background:var(--el-fill-color-light); border-radius:4px; }
.comparison-description span { font-weight:600; }
.comparison-description p { margin:0; white-space:pre-wrap; word-break:break-word; }
.comparison-matrix-wrap { overflow-x:auto; border:1px solid var(--el-border-color-lighter); }
.comparison-matrix { border-collapse:collapse; min-width:100%; table-layout:fixed; }
.comparison-matrix th,.comparison-matrix td { min-width:220px; padding:10px 12px; border-right:1px solid var(--el-border-color-lighter); border-bottom:1px solid var(--el-border-color-lighter); text-align:left; vertical-align:top; white-space:pre-wrap; word-break:break-word; }
.comparison-matrix thead th { background:var(--el-fill-color-light); }
.comparison-matrix .comparison-matrix__field { position:sticky; left:0; z-index:2; min-width:150px; width:150px; background:var(--el-fill-color-light); }
.project-selection-hint { margin-top:6px; color:var(--el-text-color-secondary); font-size:12px; }
:global(.comparison-dialog) { max-height:90vh; display:flex; flex-direction:column; overflow:hidden; }
:global(.comparison-dialog .el-dialog__header),:global(.comparison-dialog .el-dialog__footer) { flex:none; }
:global(.comparison-dialog .el-dialog__body) { flex:1; min-height:0; overflow-y:auto; }
:global(.comparison-dialog .el-dialog__footer) { border-top:1px solid var(--el-border-color-lighter); background:var(--el-fill-color-lighter); }
@media (max-width:700px) { .comparison-header { align-items:flex-start; flex-direction:column; } .comparison-header__hint { display:block; margin:4px 0 0; } .comparison-search { align-items:stretch; flex-direction:column; } }
</style>
