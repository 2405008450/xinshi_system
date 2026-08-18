<template>
  <el-card class="talent-card compact-list-card">
    <template #header>
      <div class="card-header">
        <div>
          <span class="page-title">{{ pageTitle }}</span>
          <span class="page-subtitle">人员基础资料统一维护，专业能力按需启用</span>
        </div>
        <div class="header-actions">
          <TableColumnSettings v-model="visibleColumnKeys" :columns="tableColumns" :column-count="2" @reset="resetColumns" />
          <el-button v-if="canWrite" type="primary" @click="openCreate">新增人才</el-button>
        </div>
      </div>
    </template>

    <nav class="resource-nav" aria-label="人才资源分类">
      <el-button
        v-for="item in visibleResourceViews"
        :key="item.path"
        class="resource-nav__item"
        :class="{ 'is-current': route.path === item.path }"
        :aria-current="route.path === item.path ? 'page' : undefined"
        text
        @click="router.push(item.path)"
      >
        {{ item.label }}
      </el-button>
    </nav>

    <el-form :inline="true" :model="search" class="search-form">
      <el-form-item label="关键词">
        <el-input v-model="search.keyword" clearable placeholder="姓名、编号、电话或邮箱" style="width:240px" @input="handleTextInput" @keyup.enter="searchNow" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="search.status" clearable placeholder="全部状态" style="width:140px" @change="searchNow">
          <el-option label="活跃" value="active" /><el-option label="备用" value="standby" /><el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="searchNow">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
        <el-popover v-model:visible="advancedVisible" trigger="click" placement="bottom-end" :width="760" popper-class="talent-advanced-popper">
          <template #reference><el-button>高级筛选 <el-badge v-if="advancedCount" :value="advancedCount" /></el-button></template>
          <div class="advanced-panel">
            <div class="advanced-title">高级筛选</div>
            <el-row :gutter="16">
              <el-col :xs="24" :sm="12"><el-form-item label="合作形式"><el-select v-model="search.cooperationType" clearable style="width:100%" @change="searchNow"><el-option v-for="item in cooperationOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
              <el-col :xs="24" :sm="12"><el-form-item label="行业"><el-input v-model="search.industryKeyword" clearable @input="handleTextInput" @keyup.enter="searchNow" /></el-form-item></el-col>
              <el-col :xs="24" :sm="12"><el-form-item label="待确认"><el-select v-model="search.reviewRequired" clearable style="width:100%" @change="searchNow"><el-option label="仅看待确认" :value="true" /><el-option label="仅看已确认" :value="false" /></el-select></el-form-item></el-col>
            </el-row>
            <div class="advanced-actions"><el-button link type="primary" @click="clearAdvanced">清空高级条件</el-button><el-button @click="advancedVisible=false">关闭</el-button></div>
          </div>
        </el-popover>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column type="index" label="序号" width="64" align="center" fixed="left" />
      <el-table-column v-for="column in visibleColumns" :key="column.key" :prop="column.key" :label="column.label" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="column.tooltip !== false">
        <template #header>
          <ClickableColumnHeader v-if="column.clickHint" :label="column.label" :hint="column.clickHint" />
          <span v-else>{{ column.label }}</span>
        </template>
        <template #default="{ row }">
          <el-popover v-if="column.key === 'fullName'" trigger="click" placement="left" :width="760" :title="`${row.fullName || '人才'} 人才详情`" popper-class="talent-detail-popper" @show="loadDetail(row.id)">
            <template #reference>
              <el-button type="primary" link class="talent-name-link business-clickable-cell" :title="`${row.fullName || '-'}（点击查看详情）`" @click.stop>{{ row.fullName || '-' }}</el-button>
            </template>
            <div class="detail-content" v-loading="detailLoadingId === row.id">
              <template v-if="detailFor(row)">
                <h4>基础信息</h4>
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="人才编号">{{ display(detailFor(row).resourceCode) }}</el-descriptions-item><el-descriptions-item label="姓名">{{ display(detailFor(row).fullName) }}</el-descriptions-item>
                  <el-descriptions-item label="状态">{{ statusLabel(detailFor(row).status) }}</el-descriptions-item><el-descriptions-item label="合作形式">{{ display(detailFor(row).cooperationType) }}</el-descriptions-item>
                  <el-descriptions-item label="电话">{{ display(detailFor(row).primaryPhone) }}</el-descriptions-item><el-descriptions-item label="邮箱">{{ display(detailFor(row).primaryEmail) }}</el-descriptions-item>
                  <el-descriptions-item label="能力" :span="2">{{ capabilityText(detailFor(row).capabilityTypes) }}</el-descriptions-item>
                  <el-descriptions-item label="备注" :span="2"><div class="pre-wrap">{{ display(detailFor(row).remarks) }}</div></el-descriptions-item>
                </el-descriptions>
                <h4 v-if="detailFor(row).writtenProfile">笔译能力</h4><ProfileDescription v-if="detailFor(row).writtenProfile" :profile="detailFor(row).writtenProfile" type="written" />
                <h4 v-if="detailFor(row).interpretationProfile">口译能力</h4><ProfileDescription v-if="detailFor(row).interpretationProfile" :profile="detailFor(row).interpretationProfile" type="interpretation" />
                <h4 v-if="detailFor(row).annotationProfile">标注能力</h4><ProfileDescription v-if="detailFor(row).annotationProfile" :profile="detailFor(row).annotationProfile" type="annotation" />
                <h4 v-if="detailFor(row).careerProfile">招聘职业档案</h4><ProfileDescription v-if="detailFor(row).careerProfile" :profile="detailFor(row).careerProfile" type="career" />
              </template>
            </div>
          </el-popover>
          <div v-else-if="column.key === 'capabilityTypes'" class="tag-list"><el-tag v-for="item in row.capabilityTypes" :key="item" size="small">{{ capabilityLabel(item) }}</el-tag><span v-if="!row.capabilityTypes?.length">-</span></div>
          <el-tag v-else-if="column.key === 'status'" :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          <el-tag v-else-if="column.key === 'duplicateReviewRequired' && row.duplicateReviewRequired" type="warning" size="small">待核重</el-tag>
          <span v-else-if="column.key === 'duplicateReviewRequired'">-</span>
          <span v-else>{{ tableDisplay(column, row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <div v-if="canWrite" class="action-buttons">
            <TableActionButton action="edit" @click="openEdit(row)" />
          </div>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next, jumper" class="pagination" @current-change="fetchData" @size-change="handleSizeChange" />

    <el-dialog v-model="editorVisible" :title="editorTitle" width="min(980px, calc(100vw - 32px))" top="5vh" class="talent-editor-dialog" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="105px">
        <div class="form-section"><h3>基础信息</h3>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="姓名" prop="fullName"><el-input v-model="form.fullName" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="人才编号"><el-input v-model="form.resourceCode" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option label="活跃" value="active" /><el-option label="备用" value="standby" /><el-option label="停用" value="inactive" /></el-select></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="合作形式"><el-select v-model="form.cooperationType" clearable style="width:100%"><el-option v-for="item in cooperationOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="主要电话"><el-input v-model="form.primaryPhone" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="主要邮箱"><el-input v-model="form.primaryEmail" /></el-form-item></el-col></el-row>
          <el-row :gutter="16"><el-col :xs="24" :md="12"><el-form-item label="简历路径"><el-input v-model="form.resumePath" /></el-form-item></el-col><el-col :xs="24" :md="12"><el-form-item label="其他联系方式"><el-input v-model="form.contactInfo" /></el-form-item></el-col></el-row>
          <el-form-item label="备注"><el-input v-model="form.remarks" type="textarea" :rows="2" /></el-form-item>
        </div>
        <div v-if="!isRecruitmentPool" class="form-section"><h3>专业能力</h3><el-form-item label="能力类型"><el-checkbox-group v-model="form.capabilityTypes"><el-checkbox value="written_translation">笔译</el-checkbox><el-checkbox value="interpretation">口译</el-checkbox><el-checkbox value="annotation">标注</el-checkbox></el-checkbox-group></el-form-item></div>
        <div v-if="!isRecruitmentPool && hasCapability('written_translation')" class="form-section"><h3>笔译能力</h3><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="语种方向"><el-input v-model="form.writtenProfile.languages" placeholder="例如：中英、中日" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="翻译方向"><el-input v-model="form.writtenProfile.direction" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="质量评分"><el-input v-model="form.writtenProfile.qualityScore" /></el-form-item></el-col></el-row><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="日产能"><el-input-number v-model="form.writtenProfile.dailyWordCapacity" :min="0" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="云编辑"><el-switch v-model="form.writtenProfile.canCloudEdit" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="审校"><el-switch v-model="form.writtenProfile.canRevision" /></el-form-item></el-col></el-row></div>
        <div v-if="!isRecruitmentPool && hasCapability('interpretation')" class="form-section"><h3>口译能力</h3><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="语种方向"><el-input v-model="form.interpretationProfile.languages" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="口译等级"><el-select v-model="form.interpretationProfile.interpretationLevel" clearable style="width:100%"><el-option label="初级" value="初级" /><el-option label="中级" value="中级" /><el-option label="高级" value="高级" /></el-select></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="口译方式"><el-select v-model="form.interpretationProfile.interpretationModes" multiple style="width:100%"><el-option label="同传" value="simultaneous" /><el-option label="交传" value="consecutive" /></el-select></el-form-item></el-col></el-row></div>
        <div v-if="!isRecruitmentPool && hasCapability('annotation')" class="form-section"><h3>标注能力</h3><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="任务类型"><el-select v-model="form.annotationProfile.taskTypes" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="数据模态"><el-select v-model="form.annotationProfile.dataModalities" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="工具经验"><el-select v-model="form.annotationProfile.tools" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col></el-row><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="质量评分"><el-input v-model="form.annotationProfile.qualityScore" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="日产能"><el-input-number v-model="form.annotationProfile.dailyCapacity" :min="0" style="width:100%" /></el-form-item></el-col></el-row></div>
        <div class="form-section"><h3>招聘职业档案</h3><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="行业"><el-select v-model="form.careerProfile.industries" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="职能"><el-select v-model="form.careerProfile.functions" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="8"><el-form-item label="岗位"><el-select v-model="form.careerProfile.jobTitles" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col></el-row><el-row :gutter="16"><el-col :xs="24" :md="8"><el-form-item label="工作年限"><el-input-number v-model="form.careerProfile.yearsExperience" :min="0" :precision="1" style="width:100%" /></el-form-item></el-col><el-col :xs="24" :md="16"><el-form-item label="期望地点"><el-select v-model="form.careerProfile.preferredLocations" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item></el-col></el-row></div>
      </el-form>
      <template #footer><el-button @click="editorVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElDescriptions, ElDescriptionsItem, ElMessage, ElMessageBox } from 'element-plus'
import * as talentApi from '@/api/talents'
import ClickableColumnHeader from '@/components/common/ClickableColumnHeader.vue'
import TableActionButton from '@/components/common/TableActionButton.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { hasPermission } from '@/utils/permission'

const route = useRoute(); const router = useRouter()
const resourceViews = [
  {label:'人才总库',path:'/resource-management/talents',permissions:['talents:read','translators:read']},
  {label:'笔译资源',path:'/resource-management/translators',permissions:['talents:read','translators:read']},
  {label:'口译资源',path:'/resource-management/interpreters',permissions:['talents:read','translators:read']},
  {label:'标注员',path:'/resource-management/annotators',permissions:['talents:read','translators:read']},
  {label:'招聘人才库',path:'/resource-management/recruitment-talents',permissions:['recruitment_talents:read']}
]
const visibleResourceViews = resourceViews.filter(item => hasPermission(item.permissions))
const pageTitle = computed(() => route.meta.title || '人才总库')
const capabilityType = computed(() => route.meta.capabilityType || '')
const isRecruitmentPool = computed(() => route.meta.talentApiScope === 'recruitment')
const canWrite = computed(() => isRecruitmentPool.value
  ? hasPermission(['recruitment_talents:write'])
  : hasPermission(['talents:write','translators:write']))
const talentClient = computed(() => isRecruitmentPool.value ? {
  list: talentApi.getRecruitmentTalents,
  count: talentApi.getRecruitmentTalentCount,
  detail: talentApi.getRecruitmentTalent,
  create: talentApi.createRecruitmentTalent,
  update: talentApi.updateRecruitmentTalent
} : {
  list: talentApi.getTalents,
  count: talentApi.getTalentCount,
  detail: talentApi.getTalent,
  create: talentApi.createTalent,
  update: talentApi.updateTalent
})
const cooperationOptions = ['全职','兼职','自由职业','外包']
const capabilityLabels = {written_translation:'笔译',interpretation:'口译',annotation:'标注'}
const capabilityLabel = value => capabilityLabels[value] || value
const capabilityText = values => values?.length ? values.map(capabilityLabel).join('、') : '-'
const statusLabel = value => ({active:'活跃',standby:'备用',inactive:'停用'}[value] || value || '-')
const statusType = value => ({active:'success',standby:'info',inactive:'danger'}[value] || 'info')
const display = value => value === null || value === undefined || value === '' ? '-' : Array.isArray(value) ? (value.join('、') || '-') : value
const formatDateTime = value => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}年${pad(date.getMonth()+1)}月${pad(date.getDate())}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
const tableDisplay = (column, row) => {
  if (column.key === 'yearsExperience') return row.yearsExperience === null || row.yearsExperience === undefined ? '-' : `${row.yearsExperience}年`
  if (column.type === 'datetime') return formatDateTime(row[column.key])
  return display(row[column.key])
}

const ProfileDescription = defineComponent({props:{profile:Object,type:String},setup(props){const items=computed(()=>{const p=props.profile||{};if(props.type==='written')return [['语种方向',p.languages],['翻译方向',p.direction],['质量评分',p.qualityScore],['日产能',p.dailyWordCapacity],['云编辑',p.canCloudEdit===true?'支持':p.canCloudEdit===false?'不支持':'-'],['审校',p.canRevision===true?'支持':p.canRevision===false?'不支持':'-']];if(props.type==='interpretation')return [['语种方向',p.languages],['口译等级',p.interpretationLevel],['口译方式',(p.interpretationModes||[]).map(v=>v==='simultaneous'?'同传':'交传').join('、')],['质量评分',p.qualityScore]];if(props.type==='annotation')return [['任务类型',(p.taskTypes||[]).join('、')],['数据模态',(p.dataModalities||[]).join('、')],['工具经验',(p.tools||[]).join('、')],['日产能',p.dailyCapacity]];return [['行业',(p.industries||[]).join('、')],['职能',(p.functions||[]).join('、')],['岗位',(p.jobTitles||[]).join('、')],['工作年限',p.yearsExperience],['期望地点',(p.preferredLocations||[]).join('、')],['职业概述',p.summary]]});return()=>h(ElDescriptions,{column:2,border:true,size:'small'},()=>items.value.map(([label,value])=>h(ElDescriptionsItem,{label},()=>display(value))))}})

const tableColumns=[
  {key:'resourceCode',label:'人才编号',width:130},
  {key:'fullName',label:'姓名',width:100,tooltip:false,clickHint:'点击姓名查看人才详情'},
  {key:'capabilityTypes',label:'专业能力',width:130,tooltip:false},
  {key:'languageDirections',label:'语种方向',width:180},
  {key:'industries',label:'行业',width:150},
  {key:'jobTitles',label:'岗位',width:150},
  {key:'yearsExperience',label:'工作年限',width:100},
  {key:'status',label:'状态',width:80},
  {key:'cooperationType',label:'合作形式',width:100},
  {key:'primaryPhone',label:'主要电话',width:140},
  {key:'primaryEmail',label:'主要邮箱',width:200},
  {key:'gender',label:'性别',width:80},
  {key:'nationality',label:'国籍',width:100},
  {key:'overallRating',label:'综合评级',width:120},
  {key:'firstContactDate',label:'首次联系时间',width:170,type:'datetime'},
  {key:'updatedAt',label:'最近更新',width:170,type:'datetime'},
  {key:'duplicateReviewRequired',label:'核重状态',width:100}
]
const legacyDefaultColumnKeys=['resourceCode','fullName','capabilityTypes','languageDirections','industries','status','cooperationType','primaryPhone','primaryEmail','duplicateReviewRequired']
const defaultColumnKeys=['resourceCode','fullName','capabilityTypes','languageDirections','industries','yearsExperience','status','cooperationType','primaryPhone','primaryEmail','duplicateReviewRequired']
const {selectedKeys:visibleColumnKeys,isVisible,reset:resetColumns}=useTableColumns('resource-talents-v3',tableColumns,defaultColumnKeys,{legacyDefaultKeys:legacyDefaultColumnKeys})
const visibleColumns=computed(()=>tableColumns.filter(item=>isVisible(item.key)))
const rows=ref([]);const loading=ref(false);const detailLoadingId=ref(null);const detailCache=reactive({});const pagination=reactive({page:1,limit:20,total:0});const advancedVisible=ref(false)
const search=reactive({keyword:'',status:'',cooperationType:'',industryKeyword:'',reviewRequired:null})
const advancedCount=computed(()=>['cooperationType','industryKeyword','reviewRequired'].filter(key=>search[key]!==''&&search[key]!==null).length)
let timer=null;let controller=null;let sequence=0
const params=()=>({keyword:search.keyword.trim()||undefined,status:search.status||undefined,capability_type:capabilityType.value||undefined,cooperation_type:search.cooperationType||undefined,industry_keyword:search.industryKeyword.trim()||undefined,review_required:search.reviewRequired===null?undefined:search.reviewRequired})
async function fetchData(){controller?.abort();controller=new AbortController();const current=++sequence;loading.value=true;try{const filters=params();const client=talentClient.value;const [list,count]=await Promise.all([client.list({...filters,skip:(pagination.page-1)*pagination.limit,limit:pagination.limit},{signal:controller.signal}),client.count(filters,{signal:controller.signal})]);if(current!==sequence)return;rows.value=list||[];pagination.total=count?.total||0}catch(error){if(error.code!=='ERR_CANCELED'&&current===sequence)ElMessage.error(error.detail||'加载人才数据失败')}finally{if(current===sequence)loading.value=false}}
function searchNow(){clearTimeout(timer);pagination.page=1;fetchData()}function handleTextInput(value){clearTimeout(timer);if(!value?.trim())return searchNow();timer=setTimeout(searchNow,400)}function resetSearch(){Object.assign(search,{keyword:'',status:'',cooperationType:'',industryKeyword:'',reviewRequired:null});searchNow()}function clearAdvanced(){Object.assign(search,{cooperationType:'',industryKeyword:'',reviewRequired:null});searchNow()}function handleSizeChange(){pagination.page=1;fetchData()}
async function loadDetail(id,force=false){if(!force&&detailCache[id])return detailCache[id];detailLoadingId.value=id;try{detailCache[id]=await talentClient.value.detail(id);return detailCache[id]}catch(error){ElMessage.error(error.detail||'加载人才详情失败')}finally{detailLoadingId.value=null}}
const detailFor=row=>detailCache[row.id]||row

const emptyForm=()=>({id:null,resourceCode:'',fullName:'',cooperationType:'',contactInfo:'',primaryPhone:'',primaryEmail:'',resumePath:'',remarks:'',status:'standby',capabilityTypes:capabilityType.value?[capabilityType.value]:[],writtenProfile:{languages:'',direction:'',domainSkills:[],qualityScore:'',defaultPriority:0,dailyAcceptCount:null,hourlySpeed:null,dailyWordCapacity:null,canCloudEdit:null,canRevision:null,availableTimeSlot:'',scheduleRemarks:''},interpretationProfile:{languages:'',direction:'',interpretationLevel:'',interpretationModes:[],domainSkills:[],qualityScore:'',evaluationSummary:''},annotationProfile:{taskTypes:[],dataModalities:[],tools:[],domainSkills:[],qualityScore:'',dailyCapacity:null,remarks:''},careerProfile:{industries:[],functions:[],jobTitles:[],yearsExperience:null,preferredLocations:[],expectedSalary:'',summary:''}})
const form=reactive(emptyForm());const formRef=ref(null);const editorVisible=ref(false);const saving=ref(false);const editorTitle=ref('新增人才');const rules={fullName:[{required:true,message:'请输入姓名',trigger:'blur'}]};const hasCapability=type=>form.capabilityTypes.includes(type)
function resetForm(){Object.assign(form,emptyForm());formRef.value?.clearValidate()}function openCreate(){resetForm();editorTitle.value='新增人才';editorVisible.value=true}
function fromDetail(d){const base=emptyForm();return {...base,...d,id:d.id,capabilityTypes:d.capabilityTypes||[],writtenProfile:{...base.writtenProfile,...(d.writtenProfile||{})},interpretationProfile:{...base.interpretationProfile,...(d.interpretationProfile||{})},annotationProfile:{...base.annotationProfile,...(d.annotationProfile||{})},careerProfile:{...base.careerProfile,...(d.careerProfile||{})}}}
async function openEdit(row){const detail=await loadDetail(row.id);if(!detail)return;Object.assign(form,fromDetail(detail));editorTitle.value=`编辑人才：${detail.fullName}`;editorVisible.value=true}
const payload=(allowDuplicate=false)=>({resourceCode:form.resourceCode||null,fullName:form.fullName,cooperationType:form.cooperationType||null,contactInfo:form.contactInfo||null,primaryPhone:form.primaryPhone||null,primaryEmail:form.primaryEmail||null,resumePath:form.resumePath||null,remarks:form.remarks||null,status:form.status,allowDuplicate,capabilities:form.capabilityTypes.map(capabilityType=>({capabilityType,status:'active'})),writtenProfile:hasCapability('written_translation')?form.writtenProfile:null,interpretationProfile:hasCapability('interpretation')?form.interpretationProfile:null,annotationProfile:hasCapability('annotation')?form.annotationProfile:null,careerProfile:form.careerProfile})
async function savePayload(allowDuplicate=false){const client=talentClient.value;return form.id?client.update(form.id,payload(allowDuplicate)):client.create(payload(allowDuplicate))}
async function submit(){try{await formRef.value.validate();saving.value=true;let saved;try{saved=await savePayload()}catch(error){const detail=error.detail;if(detail?.code!=='duplicate_talent')throw error;const first=detail.duplicates?.[0];try{await ElMessageBox.confirm(`发现联系方式相同的人才“${first?.fullName||first?.full_name||'未知'}”。打开已有档案，还是仍然新建？`,'疑似重复人才',{confirmButtonText:'打开已有档案',cancelButtonText:'仍然新建',distinguishCancelAndClose:true,type:'warning'});editorVisible.value=false;if(first)openEdit(first);return}catch(action){if(action==='cancel')saved=await savePayload(true);else return}}detailCache[saved.id]=saved;editorVisible.value=false;ElMessage.success('人才档案已保存');fetchData()}catch(error){if(error!==false&&error!=='cancel'&&error!=='close')ElMessage.error(error.detail?.message||error.detail||error.message||'保存失败')}finally{saving.value=false}}
watch(()=>route.path,()=>{pagination.page=1;fetchData()});onMounted(fetchData);onBeforeUnmount(()=>{clearTimeout(timer);controller?.abort()})
</script>

<style scoped>
.card-header,.header-actions,.resource-nav,.advanced-actions,.tag-list,.action-buttons{display:flex;align-items:center}.action-buttons{justify-content:center;flex-wrap:nowrap;white-space:nowrap}.card-header,.advanced-actions{justify-content:space-between}.header-actions,.tag-list{gap:8px}.page-title{font-size:18px;font-weight:600}.page-subtitle{margin-left:12px;color:var(--el-text-color-secondary);font-size:13px}.resource-nav{gap:6px;margin:-4px 0 16px;padding-bottom:10px;border-bottom:1px solid var(--el-border-color-lighter)}.resource-nav__item{margin-left:0!important;border:1px solid transparent!important;border-radius:var(--el-border-radius-base);color:var(--el-text-color-regular);font-weight:500;transition:color .2s ease,background-color .2s ease,border-color .2s ease,box-shadow .2s ease}.resource-nav__item:hover{border-color:var(--el-color-primary-light-8)!important;background:var(--el-color-primary-light-9)!important;color:var(--el-color-primary-dark-2)!important}.resource-nav__item.is-current{border-color:var(--el-color-primary-light-7)!important;background:var(--el-color-primary-light-9)!important;color:var(--el-color-primary-dark-2)!important;font-weight:600;box-shadow:inset 0 -2px 0 var(--el-color-primary)}.search-form{margin-bottom:4px}.advanced-panel{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}.advanced-title{margin-bottom:14px;font-weight:600}.pagination{justify-content:flex-end;margin-top:16px}.detail-content{max-height:560px;overflow-y:auto}.detail-content h4{margin:14px 0 8px}.detail-content h4:first-child{margin-top:0}.pre-wrap{white-space:pre-wrap;word-break:break-word}.form-section{margin-bottom:18px;padding:14px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.form-section h3{margin:0 0 14px;font-size:15px}.talent-editor-dialog{display:flex;max-height:90vh;flex-direction:column;overflow:hidden}:deep(.talent-editor-dialog .el-dialog__header),:deep(.talent-editor-dialog .el-dialog__footer){flex:0 0 auto}:deep(.talent-editor-dialog .el-dialog__body){flex:1;min-height:0;overflow-y:auto}:deep(.talent-editor-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-light);box-shadow:0 -3px 10px rgba(0,0,0,.04)}
@media(max-width:768px){.card-header{align-items:flex-start;gap:12px;flex-direction:column}.page-subtitle{display:block;margin:4px 0 0}.resource-nav{align-items:flex-start;overflow-x:auto}.search-form .el-form-item{width:100%;margin-right:0}.search-form .el-input,.search-form .el-select{width:100%!important}}
</style>

<style>
.talent-advanced-popper,.talent-detail-popper{max-width:calc(100vw - 32px)!important}.talent-detail-popper .detail-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}
</style>
