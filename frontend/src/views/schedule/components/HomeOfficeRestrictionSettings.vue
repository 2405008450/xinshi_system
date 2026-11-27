<template>
  <el-button :disabled="!!savingId" @click="open">居家办公申请设置</el-button>
  <DraggableFormDialog v-model="visible" title="居家办公申请设置" width="min(880px, calc(100vw - 32px))"
    top="5vh" append-to-body class="home-office-restrictions-dialog" @close="close">
    <p>可暂停或恢复普通居家办公申请，也可分别调减当年和明年的申请额度。</p>
    <div class="restriction-filters">
      <el-input v-model="keyword" placeholder="搜索姓名或账号" aria-label="搜索姓名或账号" clearable @keyup.enter="search" />
      <el-button @click="search">查询</el-button>
      <el-checkbox v-model="restrictedOnly">仅看已暂停</el-checkbox>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!loading && !error && !reductionReady" title="居家办公额度调减表尚未初始化" type="warning" :closable="false" />
    <DepartmentPagedList :items="filteredRows" grouped v-slot="{rows}"><el-table v-loading="loading" :data="rows" border empty-text="没有符合条件的人员">
      <el-table-column prop="name" label="姓名" min-width="120" />
      <el-table-column prop="username" label="账号" min-width="120" />
      <el-table-column label="申请限制" min-width="110">
        <template #default="{row}">
          <el-tag v-if="row.restricted" type="warning">已暂停</el-tag>
          <span v-else>未限制</span>
        </template>
      </el-table-column>
      <el-table-column v-for="year in years" :key="year" :label="`${year} 年调减`" min-width="120">
        <template #default="{row}">
          <span>{{row.reductions?.[year]?.days||0}} 天</span>
          <el-button link type="primary" :disabled="!editable||!reductionReady||!!savingId"
            :aria-label="`调整 ${row.name} ${year} 年调减天数`" @click="editReduction(row,year)">调整</el-button>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="115" fixed="right">
        <template #default="{row}">
          <el-button link :type="row.restricted?'primary':'danger'" :disabled="!editable||!!savingId"
            :loading="savingId===row.user_id" @click="save(row)">{{row.restricted?'恢复申请':'暂停申请'}}</el-button>
        </template>
      </el-table-column>
    </el-table></DepartmentPagedList>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="reductionVisible" :title="`${reductionTarget?.name||''} · ${reductionForm.year} 年额度调减`"
    width="min(520px, calc(100vw - 32px))" top="5vh" append-to-body class="home-office-restrictions-dialog"
    :close-on-click-modal="false" :before-close="closeReduction">
    <AppForm ref="formRef" :model="reductionForm" :rules="rules" label-position="top">
      <el-form-item label="调减天数" prop="days">
        <el-input-number v-model="reductionForm.days" :min="0" :max="12" :precision="0" :disabled="!!savingId" />
      </el-form-item>
      <p>填写该年度累计要调减的天数，填 0 可取消调减。调整结果会显示在员工的申请页。</p>
      <p v-if="reductionTarget?.reductions?.[reductionForm.year]?.reason">上次调整理由：{{reductionTarget.reductions[reductionForm.year].reason}}</p>
      <el-form-item label="调整理由" prop="reason">
        <el-input v-model="reductionForm.reason" type="textarea" :rows="3" maxlength="500" show-word-limit :disabled="!!savingId" />
      </el-form-item>
    </AppForm>
    <el-alert v-if="reductionError" :title="reductionError" type="error" :closable="false" />
    <template #footer>
      <el-button :disabled="!!savingId" @click="reductionVisible=false">取消</el-button>
      <el-button type="primary" :loading="!!savingId" @click="saveReduction">保存调减</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import DepartmentPagedList from '@/components/common/DepartmentPagedList.vue'
import {computed, nextTick, onBeforeUnmount, reactive, ref, watch} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {getHomeOfficeRestrictions, saveHomeOfficeRestriction, saveHomeOfficeQuotaReduction} from '@/api/attendance'
import {matchesSearchFields} from '@/utils/searchMatching'

defineProps({editable:Boolean})
const visible=ref(false), loading=ref(false), savingId=ref(''), error=ref('')
const rows=ref([]), keyword=ref(''), query=ref(''), restrictedOnly=ref(false)
const years=ref([]),reductionReady=ref(false),reductionVisible=ref(false),reductionTarget=ref(null),reductionError=ref('')
const formRef=ref(),reductionForm=reactive({year:null,days:0,reason:''})
const rules={days:[{required:true,type:'integer',min:0,max:12,message:'请输入 0 至 12 天'}],
  reason:[{required:true,whitespace:true,message:'请填写调整理由'}]}
const filteredRows=computed(()=>rows.value.filter(row=>
  (!restrictedOnly.value||row.restricted)&&matchesSearchFields([row.name,row.username],query.value)
))
let controller, searchTimer

function search(){
  clearTimeout(searchTimer)
  query.value=keyword.value
}

watch(keyword,value=>{
  clearTimeout(searchTimer)
  if(value.trim())searchTimer=setTimeout(search,400)
  else search()
})

async function open(){
  controller?.abort()
  visible.value=true
  keyword.value=''
  search()
  restrictedOnly.value=false
  rows.value=[]
  years.value=[]
  reductionReady.value=false
  error.value=''
  loading.value=true
  const request=new AbortController()
  controller=request
  try{
    const result=await getHomeOfficeRestrictions({signal:request.signal})
    if(controller===request){
      rows.value=result.people
      years.value=result.years
      reductionReady.value=result.reduction_ready
    }
  }catch(e){
    if(controller===request)error.value=e.detail||'读取申请限制失败'
  }finally{
    if(controller===request)loading.value=false
  }
}

function close(){
  controller?.abort()
  controller=null
  clearTimeout(searchTimer)
}

async function save(row){
  if(savingId.value)return
  error.value=''
  savingId.value=row.user_id
  try{
    const {restricted}=await saveHomeOfficeRestriction(row.user_id,!row.restricted)
    const current=rows.value.find(person=>person.user_id===row.user_id)
    if(current)current.restricted=restricted
    ElMessage.success(restricted?`已暂停 ${row.name} 的申请`:`已恢复 ${row.name} 的申请`)
  }catch(e){
    error.value=e.detail||'保存申请限制失败'
  }finally{
    savingId.value=''
  }
}

function editReduction(row,year){
  reductionTarget.value=row
  Object.assign(reductionForm,{year,days:row.reductions?.[year]?.days||0,reason:''})
  reductionError.value=''
  reductionVisible.value=true
  nextTick(()=>formRef.value?.clearValidate())
}

function closeReduction(done){
  if(!savingId.value)done()
}

async function saveReduction(){
  if(savingId.value||!await formRef.value.validate().catch(()=>false))return
  const row=reductionTarget.value
  const {year,days,reason}=reductionForm
  reductionError.value=''
  savingId.value=row.user_id
  try{
    const adjustment=await saveHomeOfficeQuotaReduction(row.user_id,{year,days,reason:reason.trim()})
    row.reductions={...row.reductions,[year]:adjustment}
    reductionVisible.value=false
    ElMessage.success(`已保存 ${row.name} ${year} 年额度调整`)
  }catch(e){
    reductionError.value=e.detail||'额度调减未保存'
  }finally{
    savingId.value=''
  }
}

onBeforeUnmount(close)
</script>

<style scoped>
.restriction-filters{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:12px 0}
.restriction-filters .el-input{width:min(100%,260px)}
.el-alert{margin-bottom:12px}
</style>

<style>
.home-office-restrictions-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.home-office-restrictions-dialog .el-dialog__header,.home-office-restrictions-dialog .el-dialog__footer{flex-shrink:0}
.home-office-restrictions-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.home-office-restrictions-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter)}
</style>
