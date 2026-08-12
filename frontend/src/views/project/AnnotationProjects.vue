<template>
  <el-card class="annotation-card">
    <template #header>
      <div class="card-header">
        <span>标注项目详情</span>
        <div class="header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
          <el-button v-if="canWrite" type="primary" @click="handleAdd">新增标注项目</el-button>
        </div>
      </div>
    </template>

    <el-form :inline="true" :model="searchForm" class="search-form">
      <el-form-item label="关键词">
        <el-input
          v-model="searchForm.keyword"
          placeholder="订单号、项目名称、客户名称或客户单号"
          clearable
          style="width: 320px"
          @input="handleTextSearch"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="项目状态">
        <el-select v-model="searchForm.projectStatus" clearable placeholder="全部" style="width: 150px" @change="handleSearch">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="annotation-advanced-popover">
          <template #reference>
            <el-button>高级筛选<span v-if="advancedCount" class="filter-count">{{ advancedCount }}</span></el-button>
          </template>
          <div class="advanced-panel">
            <div class="advanced-header">
              <span>高级筛选</span>
              <div>
                <el-button v-if="advancedCount" link type="primary" @click="clearAdvanced">清空高级条件</el-button>
                <el-button link @click="advancedVisible = false">关闭</el-button>
              </div>
            </div>
            <el-form label-position="top">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"><el-form-item label="项目类型"><el-select v-model="searchForm.projectType" clearable style="width:100%" @change="handleSearch"><el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="语言"><el-select v-model="searchForm.languageId" filterable clearable style="width:100%" @change="handleSearch"><el-option v-for="item in languages" :key="item.id" :label="item.label" :value="item.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="客户经理"><el-select v-model="searchForm.clientManagerId" filterable clearable style="width:100%" @change="handleSearch"><el-option v-for="item in activeUsers" :key="item.id" :label="userLabel(item)" :value="item.id" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="任务派发日期"><el-date-picker v-model="searchForm.dispatchedRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="任务提交日期"><el-date-picker v-model="searchForm.submittedRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" @change="handleSearch" /></el-form-item></el-col>
              </el-row>
            </el-form>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table :data="tableData" v-loading="loading" border class="annotation-table">
      <el-table-column type="index" label="序号" width="64" align="center" fixed="left" />
      <el-table-column label="订单号" width="190" fixed="left">
        <template #default="{ row }">
          <el-popover trigger="click" placement="left" :width="760" title="标注项目详情" popper-class="annotation-detail-popover" @show="loadDetail(row.id)">
            <template #reference><el-button type="primary" link @click.stop>{{ row.orderNo }}</el-button></template>
            <div class="detail-content" v-loading="detailLoadingId === row.id">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="客户编号">{{ textValue(detailRow(row).clientCode) }}</el-descriptions-item>
                <el-descriptions-item label="客户全称">{{ textValue(detailRow(row).clientFullName) }}</el-descriptions-item>
                <el-descriptions-item label="项目名称" :span="2">{{ textValue(detailRow(row).projectName) }}</el-descriptions-item>
                <el-descriptions-item label="项目类型" :span="2">{{ projectTypesText(detailRow(row).projectTypes) }}</el-descriptions-item>
                <el-descriptions-item label="具体任务" :span="2"><div class="pre-wrap">{{ textValue(detailRow(row).taskDescription) }}</div></el-descriptions-item>
                <el-descriptions-item label="语言方向" :span="2">{{ textValue(detailRow(row).languageItemsDisplay) }}</el-descriptions-item>
                <el-descriptions-item label="（潜在）需求量" :span="2"><div class="pre-wrap">{{ textValue(detailRow(row).potentialDemand) }}</div></el-descriptions-item>
                <el-descriptions-item label="客户单价" :span="2">
                  <div v-if="detailRow(row).priceItems?.length" class="price-detail-list">
                    <div v-for="item in detailRow(row).priceItems" :key="item.id">{{ item.display }}<span v-if="item.remarks">（{{ item.remarks }}）</span></div>
                  </div>
                  <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="任务派发时间">{{ formatDateTime(detailRow(row).taskDispatchedAt) }}</el-descriptions-item>
                <el-descriptions-item label="任务提交时间">{{ formatDateTime(detailRow(row).taskSubmittedAt) }}</el-descriptions-item>
                <el-descriptions-item label="客户经理">{{ textValue(detailRow(row).clientManagerName) }}</el-descriptions-item>
                <el-descriptions-item label="客户单号/项目标识">{{ textValue(detailRow(row).customerOrderNo) }}</el-descriptions-item>
                <el-descriptions-item v-if="detailRow(row).legacyOrderNo" label="原笔译订单号">{{ detailRow(row).legacyOrderNo }}</el-descriptions-item>
                <el-descriptions-item v-if="detailRow(row).legacyStatus" label="迁移前状态">{{ detailRow(row).legacyStatus }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column v-for="column in visibleTableColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="column.key === 'projectStatus'" :type="statusType(row.projectStatus)">{{ statusLabel(row.projectStatus) }}</el-tag>
          <span v-else-if="column.key === 'projectTypes'">{{ projectTypesText(row.projectTypes) }}</span>
          <el-popover
            v-else-if="column.key === 'clientShortName'"
            trigger="click"
            placement="bottom-start"
            :width="360"
            title="客户关联信息"
            popper-class="annotation-client-popover"
            @show="loadDetail(row.id)"
          >
            <template #reference>
              <el-button type="primary" link @click.stop>{{ textValue(row.clientShortName) }}</el-button>
            </template>
            <div v-loading="detailLoadingId === row.id">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="子客户/联系人">{{ textValue(detailRow(row).subClientContact) }}</el-descriptions-item>
                <el-descriptions-item label="客户单号/项目标识">{{ textValue(detailRow(row).customerOrderNo) }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </el-popover>
          <span v-else-if="column.type === 'datetime'">{{ formatDateTime(row[column.key]) }}</span>
          <span v-else>{{ textValue(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton v-if="canWrite" action="edit" @click="handleEdit(row)" />
          <TableActionButton v-if="canWrite" action="delete" @click="handleDelete(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @size-change="fetchData" @current-change="fetchData" />

    <el-dialog v-model="dialogVisible" class="annotation-editor-dialog" :title="dialogTitle" width="min(1080px, calc(100vw - 32px))" top="5vh" @closed="resetForm">
      <div ref="dialogBodyRef" class="editor-body">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="125px">
          <section class="form-section">
            <h3>基础与客户</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="订单号"><el-input v-model="form.orderNo" disabled placeholder="保存后自动生成" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="项目状态" prop="projectStatus"><el-select v-model="form.projectStatus" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24"><el-form-item label="项目名称"><el-input v-model="form.projectName" placeholder="可手工填写，或根据客户、方向和类型生成" @input="nameManuallyEdited=true"><template #append><el-button @click="generateProjectName">重新生成</el-button></template></el-input></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="项目类型"><el-select v-model="form.projectTypes" multiple clearable collapse-tags collapse-tags-tooltip style="width:100%"><el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户经理"><el-select v-model="form.clientManagerId" filterable clearable style="width:100%"><el-option v-for="item in activeUsers" :key="item.id" :label="userLabel(item)" :value="item.id" /></el-select></el-form-item></el-col>
            </el-row>
            <el-form-item label="具体任务"><el-input v-model="form.taskDescription" type="textarea" :rows="3" /></el-form-item>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="关联客户"><el-select v-model="form.clientId" filterable clearable style="width:100%" placeholder="选择已有客户，或在下方录入新客户" @change="handleClientChange"><el-option v-for="item in clients" :key="item.id" :label="`${item.client_short_name} · ${item.client_name}`" :value="item.id" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="子客户"><el-select v-model="form.subClientId" filterable clearable style="width:100%" @change="handleSubClientChange"><el-option v-for="item in selectedClientSubClients" :key="item.id" :label="item.client_short_name" :value="item.id" /></el-select></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="8"><el-form-item label="客户简称"><el-input v-model="form.clientShortName" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户编号"><el-input v-model="form.clientCode" /></el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="客户全称"><el-input v-model="form.clientFullName" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="子客户/联系人"><el-input v-model="form.contactName" placeholder="子客户从上方选择，联系人可在此填写" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="客户单号/标识"><el-input v-model="form.customerOrderNo" /></el-form-item></el-col>
            </el-row>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>语言方向</h3><div><el-button @click="addLanguage">新增共享语种</el-button><el-button type="primary" plain @click="addLanguageItem">添加语言项</el-button></div></div>
            <el-empty v-if="!form.languageItems.length" description="暂无语言项" :image-size="70" />
            <div v-for="(item,index) in form.languageItems" :key="index" class="language-row">
              <el-select v-model="item.mode" style="width:110px" @change="item.targetLanguageId = ''"><el-option label="单语种" value="single" /><el-option label="翻译方向" value="direction" /></el-select>
              <el-select v-model="item.sourceLanguageId" filterable placeholder="语种" style="flex:1"><el-option v-for="lang in languages" :key="lang.id" :label="lang.label" :value="lang.id"><span>{{ lang.label }}</span><el-tag v-if="lang.isCustom" size="small" type="warning" class="new-tag">新</el-tag></el-option></el-select>
              <template v-if="item.mode === 'direction'"><span class="direction-arrow">→</span><el-select v-model="item.targetLanguageId" filterable placeholder="目标语种" style="flex:1"><el-option v-for="lang in languages" :key="lang.id" :label="lang.label" :value="lang.id"><span>{{ lang.label }}</span><el-tag v-if="lang.isCustom" size="small" type="warning" class="new-tag">新</el-tag></el-option></el-select></template>
              <el-button link type="danger" @click="form.languageItems.splice(index,1)">删除</el-button>
            </div>
          </section>

          <section class="form-section">
            <div class="section-title-row"><h3>需求与客户单价</h3><el-button type="primary" plain @click="addPriceItem">添加报价</el-button></div>
            <el-form-item label="（潜在）需求量"><el-input v-model="form.potentialDemand" type="textarea" :rows="5" placeholder="可填写批次、交付周期、项目周期等完整说明" /></el-form-item>
            <el-empty v-if="!form.priceItems.length" description="暂无客户单价明细" :image-size="70" />
            <div v-for="(item,index) in form.priceItems" :key="index" class="price-card">
              <div class="repeat-title"><span>报价 {{ index + 1 }}</span><el-button link type="danger" @click="form.priceItems.splice(index,1)">删除</el-button></div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="8"><el-form-item label="项目类型" label-width="80px"><el-select v-model="item.projectType" clearable style="width:100%"><el-option v-for="type in selectedProjectTypeOptions" :key="type.value" :label="type.label" :value="type.value" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="语言范围" label-width="80px"><el-select v-model="item.languageKey" clearable style="width:100%"><el-option v-for="language in currentLanguageOptions" :key="language.key" :label="language.label" :value="language.key" /></el-select></el-form-item></el-col>
                <el-col :xs="24" :md="8"><el-form-item label="金额" label-width="60px"><el-input-number v-model="item.amount" :min="0.000001" :precision="6" :controls="false" style="width:100%" /></el-form-item></el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :xs="24" :md="6"><el-form-item label="币种" label-width="60px"><el-input v-model="item.currency" maxlength="3" /></el-form-item></el-col>
                <el-col :xs="24" :md="6"><el-form-item label="单位" label-width="60px"><el-input v-model="item.unit" placeholder="条/小时/分钟等" /></el-form-item></el-col>
                <el-col :xs="24" :md="12"><el-form-item label="备注" label-width="60px"><el-input v-model="item.remarks" /></el-form-item></el-col>
              </el-row>
            </div>
          </section>

          <section class="form-section">
            <h3>任务时间</h3>
            <el-row :gutter="16">
              <el-col :xs="24" :md="12"><el-form-item label="任务派发时间"><el-date-picker v-model="form.taskDispatchedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col>
              <el-col :xs="24" :md="12"><el-form-item label="任务提交时间"><el-date-picker v-model="form.taskSubmittedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item></el-col>
            </el-row>
          </section>
        </el-form>
      </div>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as annotationApi from '@/api/annotationProjects'
import * as clientApi from '@/api/clients'
import * as userApi from '@/api/users'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'
import TableActionButton from '@/components/common/TableActionButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'

const canWrite = hasPermission('projects:write')
const projectTypeOptions = [
  ['audio_collection','音频采集'],['audio_annotation','音频标注'],['audio_evaluation','音频评测'],['text_evaluation','文本评测'],['text_annotation','文本标注'],['quality_inspection','质检'],['listening_test','测听'],['slot_deduction','扣槽'],['generalization','泛化'],['translation','翻译'],
].map(([value,label]) => ({ value,label }))
const projectTypeMap = Object.fromEntries(projectTypeOptions.map((item) => [item.value,item.label]))
const statusOptions = [
  ['pending_confirmation','待确认'],['trial','试标中'],['in_progress','进行中'],['sent_to_client','已发客户'],['client_feedback','客户反馈'],['cancelled','已取消'],['partially_cancelled','已部分取消'],
].map(([value,label]) => ({ value,label }))
const statusMap = Object.fromEntries(statusOptions.map((item) => [item.value,item.label]))

const tableColumns = [
  { key:'projectName',label:'项目名称',minWidth:210 },{ key:'projectTypes',label:'项目类型',minWidth:180 },{ key:'taskDescription',label:'具体任务',minWidth:190 },{ key:'projectStatus',label:'项目状态',width:120 },{ key:'clientShortName',label:'客户简称',width:140 },{ key:'languageItemsDisplay',label:'语言方向',minWidth:200 },{ key:'potentialDemand',label:'（潜在）需求量',minWidth:240 },{ key:'customerPriceSummary',label:'客户单价',minWidth:220 },{ key:'taskDispatchedAt',label:'任务派发时间',width:180,type:'datetime' },{ key:'taskSubmittedAt',label:'任务提交时间',width:180,type:'datetime' },{ key:'clientManagerName',label:'客户经理',width:130 },
]
const defaultColumns = tableColumns.map((item) => item.key)
const { selectedKeys: visibleColumnKeys, isVisible, reset: resetColumns } = useTableColumns('annotation-details-v1',tableColumns,defaultColumns)
const visibleTableColumns = computed(() => tableColumns.filter((item) => isVisible(item.key)))

const loading=ref(false), dialogVisible=ref(false), submitLoading=ref(false), advancedVisible=ref(false)
const dialogTitle=ref('新增标注项目'), formRef=ref(), dialogBodyRef=ref(), detailLoadingId=ref(null)
const tableData=ref([]), clients=ref([]), users=ref([]), languages=ref([])
const detailCache=reactive({}), pagination=reactive({page:1,limit:10,total:0})
const searchForm=reactive({keyword:'',projectStatus:'',projectType:'',languageId:'',clientManagerId:'',dispatchedRange:[],submittedRange:[]})
let requestController, requestId=0, searchTimer
let autoNameTimer
const nameManuallyEdited=ref(false)

const emptyForm=()=>({id:'',orderNo:'',projectName:'',projectTypes:[],taskDescription:'',clientId:'',subClientId:'',clientShortName:'',clientCode:'',clientFullName:'',contactName:'',customerOrderNo:'',projectStatus:'pending_confirmation',potentialDemand:'',taskDispatchedAt:'',taskSubmittedAt:'',clientManagerId:'',languageItems:[],priceItems:[]})
const form=reactive(emptyForm())
const rules={projectStatus:[{required:true,message:'请选择项目状态',trigger:'change'}]}
const activeUsers=computed(()=>users.value.filter((item)=>item.is_active ?? item.isActive ?? true))
const selectedClient=computed(()=>clients.value.find((item)=>item.id===form.clientId))
const selectedClientSubClients=computed(()=>selectedClient.value?.sub_clients||[])
const selectedProjectTypeOptions=computed(()=>projectTypeOptions.filter((item)=>form.projectTypes.includes(item.value)))
const currentLanguageOptions=computed(()=>form.languageItems.filter((item)=>item.sourceLanguageId && (item.mode==='single'||item.targetLanguageId)).map((item)=>({key:`${item.sourceLanguageId}:${item.mode==='direction'?item.targetLanguageId:''}`,label:languageItemLabel(item)})))
const advancedCount=computed(()=>[searchForm.projectType,searchForm.languageId,searchForm.clientManagerId,searchForm.dispatchedRange?.length?'d':'',searchForm.submittedRange?.length?'s':''].filter(Boolean).length)

const userLabel=(item)=>item.full_name||item.fullName||item.username
const textValue=(value)=>value===null||value===undefined||value===''?'-':String(value)
const formatDateTime=(value)=>{if(!value)return '-';const date=new Date(String(value).replace(' ','T'));return Number.isNaN(date.getTime())?String(value):date.toLocaleString('zh-CN',{hour12:false})}
const projectTypesText=(values)=>Array.isArray(values)&&values.length?values.map((value)=>projectTypeMap[value]||value).join('；'):'-'
const statusLabel=(value)=>statusMap[value]||value||'-'
const statusType=(value)=>({pending_confirmation:'info',trial:'warning',in_progress:'primary',sent_to_client:'success',client_feedback:'warning',cancelled:'danger',partially_cancelled:'warning'}[value]||'info')
const languageName=(id)=>languages.value.find((item)=>item.id===id)?.label||''
const languageItemLabel=(item)=>item.mode==='direction'?`${languageName(item.sourceLanguageId)}→${languageName(item.targetLanguageId)}`:languageName(item.sourceLanguageId)
const detailRow=(row)=>detailCache[row.id]||row

const buildFilters=()=>{const [ds,de]=searchForm.dispatchedRange||[],[ss,se]=searchForm.submittedRange||[];return {keyword:searchForm.keyword.trim()||undefined,project_status:searchForm.projectStatus||undefined,project_type:searchForm.projectType||undefined,language_id:searchForm.languageId||undefined,client_manager_id:searchForm.clientManagerId||undefined,dispatched_date_start:ds||undefined,dispatched_date_end:de||undefined,submitted_date_start:ss||undefined,submitted_date_end:se||undefined}}
const fetchData=async()=>{requestController?.abort();requestController=new AbortController();const current=++requestId;loading.value=true;const filters=buildFilters();try{const [rows,count]=await Promise.all([annotationApi.getAnnotationProjects({skip:(pagination.page-1)*pagination.limit,limit:pagination.limit,...filters},{signal:requestController.signal}),annotationApi.getAnnotationProjectCount(filters,{signal:requestController.signal})]);if(current!==requestId)return;tableData.value=Array.isArray(rows)?rows:[];pagination.total=count?.total||0}catch(error){if(current!==requestId||error?.code==='ERR_CANCELED')return;ElMessage.error(error.detail||'加载标注项目失败')}finally{if(current===requestId)loading.value=false}}
const handleSearch=()=>{clearTimeout(searchTimer);pagination.page=1;fetchData()}
const handleTextSearch=(value)=>{clearTimeout(searchTimer);if(!value?.trim())return handleSearch();searchTimer=setTimeout(handleSearch,400)}
const clearAdvanced=()=>{Object.assign(searchForm,{projectType:'',languageId:'',clientManagerId:'',dispatchedRange:[],submittedRange:[]});handleSearch()}
const resetSearch=()=>{Object.assign(searchForm,{keyword:'',projectStatus:'',projectType:'',languageId:'',clientManagerId:'',dispatchedRange:[],submittedRange:[]});handleSearch()}
const loadReferenceData=async()=>{const results=await Promise.allSettled([clientApi.getClients({skip:0,limit:500,frequent_first:true}),userApi.getUsers({skip:0,limit:500}),getProjectLanguages()]);clients.value=results[0].status==='fulfilled'&&Array.isArray(results[0].value)?results[0].value:[];users.value=results[1].status==='fulfilled'&&Array.isArray(results[1].value)?results[1].value:[];languages.value=results[2].status==='fulfilled'?results[2].value:[]}
const loadDetail=async(id,force=false)=>{if(!force&&detailCache[id])return detailCache[id];detailLoadingId.value=id;try{const detail=await annotationApi.getAnnotationProject(id);detailCache[id]=detail;return detail}catch(error){ElMessage.error(error.detail||'加载项目详情失败');return null}finally{detailLoadingId.value=null}}

const handleClientChange=(id)=>{const client=clients.value.find((item)=>item.id===id);form.subClientId='';if(!client)return;form.clientShortName=client.client_short_name||'';form.clientFullName=client.client_name||'';form.clientCode=client.client_code||''}
const handleSubClientChange=(id)=>{const subClient=selectedClientSubClients.value.find((item)=>item.id===id);if(subClient){form.clientShortName=subClient.client_short_name||'';form.clientFullName=subClient.client_name||'';form.clientCode=subClient.sub_client_code||''}else if(form.clientId){handleClientChange(form.clientId)}}
const addLanguageItem=()=>form.languageItems.push({mode:'single',sourceLanguageId:'',targetLanguageId:''})
const addPriceItem=()=>form.priceItems.push({projectType:'',languageKey:'',amount:null,currency:'CNY',unit:'',remarks:''})
const addLanguage=async()=>{try{const {value}=await ElMessageBox.prompt('请输入要新增的语种或方言名称','新增共享语种',{inputPlaceholder:'例如：粤语',inputValidator:(text)=>!!text?.trim()||'语种名称不能为空'});const created=await createProjectLanguage(value.trim());languages.value.push(created);ElMessage.success('语种已新增并标记为“新”')}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error.detail||'新增语种失败')}}
const normalizedLanguageItems=()=>form.languageItems.filter((item)=>item.sourceLanguageId).map((item)=>({sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.mode==='direction'?(item.targetLanguageId||null):null}))
const splitLanguageKey=(key)=>{if(!key)return {sourceLanguageId:null,targetLanguageId:null};const [source,target]=key.split(':');return {sourceLanguageId:source||null,targetLanguageId:target||null}}
const validateLanguageItems=()=>{for(const item of form.languageItems){if(!item.sourceLanguageId)throw new Error('每个语言项都必须选择语种');if(item.mode==='direction'&&!item.targetLanguageId)throw new Error('翻译方向必须选择目标语种');if(item.targetLanguageId===item.sourceLanguageId)throw new Error('语言方向的两个语种不能相同')}const keys=normalizedLanguageItems().map((item)=>`${item.sourceLanguageId}:${item.targetLanguageId||''}`);if(new Set(keys).size!==keys.length)throw new Error('同一语言或语言方向不能重复')}
const validateFormData=()=>{validateLanguageItems();if(form.taskDispatchedAt&&form.taskSubmittedAt&&new Date(form.taskSubmittedAt)<new Date(form.taskDispatchedAt))throw new Error('任务提交时间不能早于任务派发时间');const languageKeys=new Set(currentLanguageOptions.value.map((item)=>item.key));for(const item of form.priceItems){if(item.projectType&&!form.projectTypes.includes(item.projectType))throw new Error('报价引用了当前项目未选择的项目类型');if(item.languageKey&&!languageKeys.has(item.languageKey))throw new Error('报价引用了当前项目未选择的语言项');if(!item.amount||item.amount<=0)throw new Error('报价金额必须大于零');if(!item.currency?.trim()||item.currency.trim().length!==3)throw new Error('报价币种必须为三位代码');if(!item.unit?.trim())throw new Error('报价必须填写计价单位')}}
const buildPayload=()=>{validateFormData();return {projectName:form.projectName?.trim()||null,projectTypes:form.projectTypes,taskDescription:form.taskDescription?.trim()||null,clientId:form.clientId||null,subClientId:form.subClientId||null,clientName:form.clientFullName?.trim()||null,clientShortName:form.clientShortName?.trim()||null,clientCode:form.clientCode?.trim()||null,contactName:form.contactName?.trim()||null,customerOrderNo:form.customerOrderNo?.trim()||null,projectStatus:form.projectStatus,potentialDemand:form.potentialDemand?.trim()||null,taskDispatchedAt:form.taskDispatchedAt||null,taskSubmittedAt:form.taskSubmittedAt||null,clientManagerId:form.clientManagerId||null,languageItems:normalizedLanguageItems(),priceItems:form.priceItems.map((item)=>({projectType:item.projectType||null,...splitLanguageKey(item.languageKey),amount:item.amount,currency:item.currency.trim().toUpperCase(),unit:item.unit.trim(),remarks:item.remarks?.trim()||null}))}}
const generateProjectName=async()=>{try{validateLanguageItems();const result=await annotationApi.previewAnnotationProjectName({clientShortName:form.clientShortName?.trim()||null,projectTypes:form.projectTypes,languageItems:normalizedLanguageItems()});form.projectName=result.projectName;nameManuallyEdited.value=false;ElMessage.success('项目名称已生成，仍可手工修改')}catch(error){ElMessage.warning(error.detail||error.message||'无法生成项目名称')}}
const assignForm=(detail)=>{Object.assign(form,emptyForm(),{...detail,projectName:detail.projectName||'',clientId:detail.clientId||'',subClientId:detail.subClientId||'',clientShortName:detail.clientShortName||'',clientCode:detail.clientCode||'',clientFullName:detail.clientFullName||'',contactName:detail.contactName||'',customerOrderNo:detail.customerOrderNo||'',potentialDemand:detail.potentialDemand||'',taskDispatchedAt:detail.taskDispatchedAt||'',taskSubmittedAt:detail.taskSubmittedAt||'',clientManagerId:detail.clientManagerId||'',languageItems:(detail.languageItems||[]).map((item)=>({mode:item.targetLanguageId?'direction':'single',sourceLanguageId:item.sourceLanguageId,targetLanguageId:item.targetLanguageId||''})),priceItems:(detail.priceItems||[]).map((item)=>({projectType:item.projectType||'',languageKey:item.sourceLanguageId?`${item.sourceLanguageId}:${item.targetLanguageId||''}`:'',amount:Number(item.amount),currency:item.currency||'CNY',unit:item.unit||'',remarks:item.remarks||''}))});nameManuallyEdited.value=!!detail.projectName}
const handleAdd=()=>{dialogTitle.value='新增标注项目';resetForm();nameManuallyEdited.value=false;dialogVisible.value=true}
const handleEdit=async(row)=>{const detail=await loadDetail(row.id,true);if(!detail)return;dialogTitle.value=`编辑标注项目 · ${detail.orderNo}`;assignForm(detail);dialogVisible.value=true}
const handleSubmit=async()=>{const valid=await formRef.value?.validate().catch(()=>false);if(!valid)return;submitLoading.value=true;try{const payload=buildPayload();const saved=form.id?await annotationApi.updateAnnotationProject(form.id,payload):await annotationApi.createAnnotationProject(payload);if(form.id)delete detailCache[form.id];if(saved?.id)detailCache[saved.id]=saved;ElMessage.success(form.id?'标注项目已更新':'标注项目已创建');dialogVisible.value=false;await fetchData()}catch(error){ElMessage.error(error.detail||error.message||'保存失败');dialogBodyRef.value?.scrollTo({top:0,behavior:'smooth'})}finally{submitLoading.value=false}}
const handleDelete=async(row)=>{try{await ElMessageBox.confirm(`确定删除标注项目“${row.orderNo}”吗？`,'删除确认',{type:'warning'});await annotationApi.deleteAnnotationProject(row.id);delete detailCache[row.id];ElMessage.success('删除成功');await fetchData()}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error.detail||'删除失败')}}
const resetForm=()=>{Object.assign(form,emptyForm());nameManuallyEdited.value=false;formRef.value?.clearValidate()}

watch(()=>[form.clientShortName,[...form.projectTypes],form.languageItems.map((item)=>`${item.mode}:${item.sourceLanguageId}:${item.targetLanguageId}`).join('|')],()=>{clearTimeout(autoNameTimer);if(nameManuallyEdited.value||!dialogVisible.value)return;autoNameTimer=setTimeout(()=>{const labels=form.languageItems.map(languageItemLabel).filter(Boolean);const directionSummary=labels.length>3?`${labels.slice(0,3).join('、')}等方向`:labels.join('、');const typeSummary=form.projectTypes.map((value)=>projectTypeMap[value]||value).join('、');form.projectName=[form.clientShortName?.trim(),directionSummary,typeSummary].filter(Boolean).join('-')},300)},{deep:true})

onMounted(async()=>{await loadReferenceData();await fetchData()})
onBeforeUnmount(()=>{clearTimeout(searchTimer);clearTimeout(autoNameTimer);requestController?.abort()})
</script>

<style scoped>
.card-header,.header-actions,.advanced-header,.section-title-row,.language-row,.repeat-title{display:flex;align-items:center}.card-header,.advanced-header,.section-title-row,.repeat-title{justify-content:space-between}.header-actions{gap:8px}.filter-count{display:inline-flex;min-width:18px;height:18px;margin-left:5px;padding:0 5px;align-items:center;justify-content:center;border-radius:9px;color:#fff;background:var(--el-color-primary);font-size:11px}.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-header{margin-bottom:12px;font-weight:600}.pagination{margin-top:20px}.form-section{margin-bottom:18px;padding:16px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.form-section h3{margin:0 0 16px;font-size:16px}.section-title-row{margin-bottom:12px}.section-title-row h3{margin:0}.language-row{gap:10px;margin-bottom:10px}.direction-arrow{color:var(--el-color-primary);font-size:20px;font-weight:700}.new-tag{float:right;margin-left:8px}.price-card{margin-bottom:12px;padding:12px 12px 0;border:1px solid var(--el-border-color-lighter);border-radius:6px;background:var(--el-fill-color-light)}.repeat-title{margin-bottom:8px;font-weight:600}.pre-wrap{white-space:pre-wrap;word-break:break-word}.price-detail-list>div+div{margin-top:4px}
</style>

<style>
.annotation-advanced-popover,.annotation-detail-popover,.annotation-client-popover{max-width:calc(100vw - 32px)!important}.annotation-detail-popover .detail-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.annotation-detail-popover .el-descriptions__content,.annotation-client-popover .el-descriptions__content{white-space:normal;word-break:break-word}.annotation-editor-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}.annotation-editor-dialog .el-dialog__header,.annotation-editor-dialog .el-dialog__footer{flex:0 0 auto}.annotation-editor-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto;padding-top:12px}.annotation-editor-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);box-shadow:0 -3px 10px rgba(0,0,0,.04)}
</style>
