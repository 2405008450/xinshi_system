<template>
  <el-card class="recruitment-requirements">
    <template #header><div class="requirement-header"><strong>招聘需求</strong><div><el-button v-if="!deleteMode" type="primary" @click="open()">新增招聘需求</el-button><TableColumnSettings v-if="!deleteMode" settings-key="hr-recruitment-requirements" v-model="columnKeys" :columns="columns" title="招聘需求列表字段" @reset="resetColumns" /><BatchDeleteToolbar :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" /></div></div></template>
    <div class="requirement-filters"><el-input v-model="keyword" placeholder="搜索编号、日期、城市、岗位、原因、人数、具体需求" clearable aria-label="招聘需求搜索" @keyup.enter="search" @clear="search" /><el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table ref="tableRef" :data="items" row-key="id" border v-loading="loading" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" />
      <el-table-column v-if="isVisible('demand_no')" column-key="demand_no" prop="demand_no" label="需求编号" min-width="165" />
      <el-table-column v-if="isVisible('request_date')" column-key="request_date" prop="request_date" label="需求日期" width="120" />
      <el-table-column v-if="isVisible('recruitment_city')" column-key="recruitment_city" prop="recruitment_city" label="招聘城市" min-width="120"><template #default="{row}">{{row.recruitment_city||'未填写'}}</template></el-table-column>
      <el-table-column v-if="isVisible('position')" column-key="position" prop="position" label="招聘岗位" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="isVisible('reason')" column-key="reason" prop="reason" label="招聘原因" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="isVisible('headcount')" column-key="headcount" prop="headcount" label="招聘人数" width="110" />
      <el-table-column v-if="isVisible('details')" column-key="details" label="具体需求" min-width="360"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760"><template #reference><button type="button" class="requirement-details-preview" :aria-label="`展开具体需求 ${row.demand_no}`"><span>{{row.details}}</span><em>展开具体需求</em></button></template><div class="requirement-detail"><h4>{{row.position}} · 具体需求</h4><p class="requirement-full-text">{{row.details}}</p></div></el-popover></template></el-table-column>
      <el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><el-popover trigger="click" placement="left" :width="760"><template #reference><el-button link type="primary">查看详情</el-button></template><div class="requirement-detail"><h4>{{row.demand_no}} · 招聘需求详情</h4><el-descriptions :column="2" border size="small"><el-descriptions-item label="需求编号">{{row.demand_no}}</el-descriptions-item><el-descriptions-item label="需求日期">{{row.request_date}}</el-descriptions-item><el-descriptions-item label="招聘城市">{{row.recruitment_city||'未填写'}}</el-descriptions-item><el-descriptions-item label="招聘岗位">{{row.position}}</el-descriptions-item><el-descriptions-item label="招聘人数">{{row.headcount}}</el-descriptions-item><el-descriptions-item label="招聘原因" :span="2">{{row.reason}}</el-descriptions-item><el-descriptions-item label="具体需求" :span="2"><span class="requirement-full-text">{{row.details}}</span></el-descriptions-item><el-descriptions-item label="创建时间">{{formatBusinessDateTime(row.created_at)}}</el-descriptions-item><el-descriptions-item label="更新时间">{{formatBusinessDateTime(row.updated_at)}}</el-descriptions-item></el-descriptions></div></el-popover></template></el-table-column>
      <el-table-column v-if="!deleteMode" label="操作" fixed="right" width="100"><template #default="{row}"><el-button link type="primary" @click="open(row)">编辑</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="pagination.page" :page-size="pagination.limit" :total="pagination.total" layout="total, prev, pager, next" @current-change="load" />
    <DraggableFormDialog v-model="visible" :title="target?'编辑招聘需求':'新增招聘需求'" class="recruitment-requirement-dialog" width="min(960px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close" destroy-on-close>
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" placeholder="搜索需求日期、岗位、具体需求等" :title="target?'编辑招聘需求':'新增招聘需求'" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body"><AppForm ref="formRef" :model="form" :rules="rules" label-position="top" class="requirement-grid">
        <el-form-item label="需求编号"><ReadonlyField :model-value="form.demand_no||'保存后自动生成'" source="auto" /></el-form-item>
        <el-form-item label="需求日期" prop="request_date"><el-date-picker v-model="form.request_date" type="date" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" :disabled="saving" :clearable="false" /></el-form-item>
        <el-form-item label="招聘城市" prop="recruitment_city"><el-select v-model="form.recruitment_city" filterable allow-create default-first-option clearable placeholder="选择或输入招聘城市" :disabled="saving" style="width:100%" @visible-change="value=>value&&loadCities()"><el-option v-for="office in cityOptions" :key="office.id" :label="office.city" :value="office.city" /></el-select></el-form-item>
        <el-form-item label="招聘岗位" prop="position"><el-input v-model="form.position" maxlength="200" :disabled="saving" /></el-form-item>
        <el-form-item label="招聘人数" prop="headcount"><el-input-number v-model="form.headcount" :min="1" :max="100000" :precision="0" :disabled="saving" /></el-form-item>
        <el-form-item label="招聘原因" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="2000" show-word-limit :disabled="saving" /></el-form-item>
        <el-form-item label="具体需求" prop="details" class="requirement-double-width"><el-input v-model="form.details" type="textarea" :rows="expanded?12:4" maxlength="20000" show-word-limit :disabled="saving" /><el-button link type="primary" @click="expanded=!expanded">{{expanded?'收起具体需求':'展开具体需求编辑'}}</el-button></el-form-item>
      </AppForm><p class="requirement-note">需求编号如 RT-261029-001：保存时按需求日期分日顺序生成；编辑需求日期不改变已有编号。</p><el-alert v-if="saveError" :title="saveError" type="error" :closable="false" /></div>
      <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存招聘需求</el-button></template>
    </DraggableFormDialog>
  </el-card>
</template>
<script setup>
import {ref,reactive,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {useTableColumns} from '@/composables/useTableColumns'
import {useBatchDelete} from '@/composables/useBatchDelete'
import {getRecruitmentRequirements,createRecruitmentRequirement,updateRecruitmentRequirement,deleteRecruitmentRequirement} from '@/api/hrRecruitment'
import {getOfficeCities} from '@/api/offices'
import {formatBusinessDateTime,businessDateTimeInputValue} from '@/utils/dateTime'
const emit=defineEmits(['changed'])
const items=ref([]),loading=ref(false),error=ref(''),keyword=ref(''),tableRef=ref(),pagination=reactive({page:1,limit:20,total:0}),visible=ref(false),target=ref(null),saving=ref(false),saveError=ref(''),formRef=ref(),body=ref(),expanded=ref(false)
const columns=[{key:'demand_no',label:'需求编号'},{key:'request_date',label:'需求日期'},{key:'recruitment_city',label:'招聘城市'},{key:'position',label:'招聘岗位'},{key:'reason',label:'招聘原因'},{key:'headcount',label:'招聘人数'},{key:'details',label:'具体需求'}]
const {selectedKeys:columnKeys,isVisible,reset:resetColumns}=useTableColumns('hr-recruitment-requirements',columns,columns.map(row=>row.key),{legacyDefaultKeys:['demand_no','request_date','position','reason','headcount','details']})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const form=reactive({id:'hr-recruitment-new',demand_no:'',request_date:'',recruitment_city:'',position:'',reason:'',headcount:1,details:''})
const rules={request_date:[{required:true,message:'请选择需求日期',trigger:'change'}],position:[{required:true,whitespace:true,message:'请填写招聘岗位',trigger:'blur'}],reason:[{required:true,whitespace:true,message:'请填写招聘原因',trigger:'blur'}],headcount:[{required:true,type:'number',min:1,message:'招聘人数至少1人',trigger:'change'}],details:[{required:true,whitespace:true,message:'请填写具体需求',trigger:'blur'}]}
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows:items,tableRef,pagination,deleteRow:deleteRecruitmentRequirement,getLabel:row=>row.demand_no,reload:()=>{emit('changed');return load()},entityName:'招聘需求'})
const cityOptions=ref([])
let cityController,citySequence=0
async function loadCities(){cityController?.abort();cityController=new AbortController();const seq=++citySequence;try{const value=await getOfficeCities({signal:cityController.signal});if(alive&&seq===citySequence)cityOptions.value=value.items||[]}catch{}}
let controller,sequence=0,timer,alive=true,clientId=''
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';try{const value=await getRecruitmentRequirements({keyword:keyword.value,page:pagination.page,limit:pagination.limit},{signal:controller.signal});if(alive&&id===sequence){items.value=value.items;pagination.total=value.total}}catch(e){if(alive&&id===sequence&&e.code!=='ERR_CANCELED')error.value=typeof e.detail==='string'?e.detail:'读取招聘需求失败'}finally{if(alive&&id===sequence)loading.value=false}}
function search(){clearTimeout(timer);if(deleteMode.value&&!deleting.value)exitDeleteMode();pagination.page=1;load()}
function reset(){keyword.value='';search()}
function open(row){target.value=row||null;Object.assign(form,{id:row?`hr-recruitment:${row.id}`:'hr-recruitment-new',demand_no:row?.demand_no||'',request_date:row?.request_date||businessDateTimeInputValue(new Date()).slice(0,10),recruitment_city:row?.recruitment_city||'',position:row?.position||'',reason:row?.reason||'',headcount:row?.headcount||1,details:row?.details||''});clientId=crypto.randomUUID();expanded.value=false;saveError.value='';clearFieldSearch();visible.value=true}
function close(done){if(!saving.value)done()}
async function save(){if(saving.value||!await formRef.value.validate().catch(()=>false))return;saving.value=true;saveError.value='';const data={request_date:form.request_date,recruitment_city:form.recruitment_city||'',position:form.position,reason:form.reason,headcount:form.headcount,details:form.details};try{if(target.value)await updateRecruitmentRequirement(target.value.id,{...data,revision:target.value.revision});else await createRecruitmentRequirement({...data,client_id:clientId});ElMessage.success('招聘需求已保存');visible.value=false;emit('changed');search()}catch(e){saveError.value=typeof e.detail==='string'?e.detail:'招聘需求未确认保存，请重试'}finally{saving.value=false}}
watch(keyword,value=>{clearTimeout(timer);if(!value)search();else timer=setTimeout(search,400)})
onMounted(()=>{load();loadCities();window.addEventListener('office-cities-changed',loadCities)});onBeforeUnmount(()=>{alive=false;sequence++;citySequence++;cityController?.abort();window.removeEventListener('office-cities-changed',loadCities);controller?.abort();clearTimeout(timer)})
</script>
<style scoped>.requirement-header,.requirement-header>div,.requirement-filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.requirement-header{justify-content:space-between}.requirement-filters{margin-bottom:14px}.requirement-filters>.el-input{width:400px;max-width:100%}.el-pagination{margin-top:14px}.requirement-details-preview{display:block;width:100%;border:0;background:transparent;text-align:left;cursor:pointer;color:inherit;font:inherit}.requirement-details-preview>span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;white-space:pre-wrap}.requirement-details-preview em{color:var(--el-color-primary);font-style:normal;font-size:12px}.requirement-detail{max-height:560px;overflow-y:auto;overflow-wrap:anywhere}.requirement-full-text{white-space:pre-wrap;overflow-wrap:anywhere}.requirement-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}.requirement-double-width{grid-column:span 2}.requirement-grid :deep(.el-date-editor){width:100%}.requirement-note{color:#64748b;font-size:13px}@media(max-width:680px){.requirement-grid{grid-template-columns:1fr}.requirement-double-width{grid-column:span 1}}</style>
<style>.recruitment-requirement-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.recruitment-requirement-dialog>.el-dialog__header,.recruitment-requirement-dialog>.el-dialog__footer{flex-shrink:0}.recruitment-requirement-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.recruitment-requirement-dialog>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
