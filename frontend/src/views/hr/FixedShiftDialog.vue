<template>
  <DraggableFormDialog v-model="visible" title="固定班次人员" data-auto-draft="off" width="min(1040px, calc(100vw - 32px))" top="5vh" class="fixed-shift-dialog" :close-on-click-modal="false" :before-close="beforeClose" destroy-on-close>
    <div v-loading="loading">
      <el-alert title="固定早早班、管理/管培生和灵活班次仅在此配置，不进入轮班表；居家班次（轮班）保留在排班表，按当周早晚班时间打卡，并标记居家。其他固定班次仍自动放入固定单元格。" type="info" :closable="false" />
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <div class="fixed-filter"><el-input v-model="keyword" placeholder="搜索姓名、账号或部门" clearable aria-label="搜索固定班次人员" @keyup.enter="applySearch" @clear="applySearch" /><el-button @click="applySearch">查询</el-button><el-checkbox v-model="onlyFixed">仅看固定人员</el-checkbox><span>固定 {{Object.keys(settings).length}} 人</span></div>
      <AppForm inline label-width="auto" class="fixed-batch">
        <el-form-item label="批量部门"><el-select v-model="batchDepartment" placeholder="选择部门" aria-label="批量固定部门" @change="batchShift='' "><el-option v-for="item in config.departments" :key="item.code" :value="item.code" :label="item.label" /></el-select></el-form-item>
        <el-form-item label="批量班次"><el-select v-model="batchShift" placeholder="选择班次" aria-label="批量固定班次"><el-option v-for="item in config.shifts" :key="item.code" :value="item.code" :label="item.label" :disabled="!validCell(batchDepartment,item.code)" /></el-select></el-form-item>
        <el-button :disabled="!selected.length||!batchDepartment||!batchShift||saving" @click="batchSet">设为固定（{{selected.length}}人）</el-button><el-button :disabled="!selected.length||saving" @click="batchClear">取消所选固定</el-button>
      </AppForm>
      <el-table ref="table" :data="filteredPeople" row-key="id" border @selection-change="selected=$event" :aria-busy="saving">
        <el-table-column type="selection" width="45" :selectable="()=>!saving" />
        <el-table-column label="姓名 / 账号" min-width="170"><template #default="{row}">{{row.name}} <small>（{{row.username}}）</small></template></el-table-column>
        <el-table-column label="所属部门" min-width="140"><template #default="{row}">{{row.departments.map(item=>item.name).join('、')}}</template></el-table-column>
        <el-table-column label="固定单元格部门" min-width="165"><template #default="{row}"><el-select :model-value="departmentFor(row)" :aria-label="`${row.name}固定部门`" :disabled="saving" placeholder="请选择固定部门" @change="setDepartment(row,$event)"><el-option v-for="item in config.departments" :key="item.code" :value="item.code" :label="item.label" /></el-select></template></el-table-column>
        <el-table-column label="固定班次" min-width="205"><template #default="{row}"><el-select :model-value="settings[row.id]?.shift||''" clearable :aria-label="`${row.name}固定班次`" :disabled="saving||!departmentFor(row)" placeholder="不固定" @update:model-value="setShift(row,$event)"><el-option v-for="item in config.shifts" :key="item.code" :value="item.code" :label="item.label" :disabled="!validCell(departmentFor(row),item.code)" /></el-select></template></el-table-column>
      </el-table>
      <p v-for="shift in config.shifts.filter(item=>['fixed_early_early','management','flexible','home_rotation'].includes(item.code))" :key="shift.code" class="fixed-note"><strong>{{shift.label}}</strong>：{{shift.description}}</p><p class="fixed-note">勾选人员可批量设置，也可逐行选择班次；班次留空表示不固定。修改后点击保存生效。</p>
    </div>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||!config.ready||!!error" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref,watch,onBeforeUnmount,reactive,toRef} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import {getFixedShiftConfig,saveFixedShiftConfig} from '@/api/monthlyShifts'
import {matchesSearchFields} from '@/utils/searchMatching'
import {useFormDraft} from '@/composables/useFormDraft'
const visible=defineModel({type:Boolean,default:false}),emit=defineEmits(['saved'])
const fixedDraft=reactive({settings:{},departments:{}}),settings=toRef(fixedDraft,'settings'),departments=toRef(fixedDraft,'departments')
const {beginDraft,pauseDraft,clearDraft}=useFormDraft({namespace:'fixed-shift-config',form:fixedDraft,createDefault:()=>({settings:{},departments:{}}),applyDraft:data=>{const valid=new Set(people.value.map(person=>person.id));fixedDraft.settings=Object.fromEntries(Object.entries(data.settings||{}).filter(([id])=>valid.has(id)));fixedDraft.departments=Object.fromEntries(Object.entries(data.departments||{}).filter(([id])=>valid.has(id)))}})
const loading=ref(false),saving=ref(false),error=ref(''),people=ref([]),selected=ref([]),keyword=ref(''),search=ref(''),onlyFixed=ref(false),batchDepartment=ref(''),batchShift=ref(''),table=ref()
const config=ref({ready:false,revision:0,departments:[],shifts:[]})
let timer,sequence=0
function applySearch(){clearTimeout(timer);search.value=keyword.value;table.value?.clearSelection()}
watch(keyword,value=>{clearTimeout(timer);if(!value)applySearch();else timer=setTimeout(applySearch,400)})
watch(onlyFixed,()=>table.value?.clearSelection())
const filteredPeople=computed(()=>people.value.filter(person=>(!onlyFixed.value||settings.value[person.id])&&matchesSearchFields([person.name,person.username,...person.departments.map(item=>item.name)],search.value)))
const validCell=(department,shift)=>shift!=='customer_remote'||department==='customer'
const departmentFor=person=>settings.value[person.id]?.department||departments.value[person.id]||person.default_department||''
function setDepartment(person,value){departments.value[person.id]=value;if(settings.value[person.id]){if(validCell(value,settings.value[person.id].shift))settings.value[person.id].department=value;else delete settings.value[person.id]}}
function setShift(person,shift){if(!shift){delete settings.value[person.id];return}settings.value[person.id]={user_id:person.id,department:departmentFor(person),shift}}
function batchSet(){for(const person of selected.value){departments.value[person.id]=batchDepartment.value;settings.value[person.id]={user_id:person.id,department:batchDepartment.value,shift:batchShift.value}}}
function batchClear(){for(const person of selected.value)delete settings.value[person.id]}
function beforeClose(done){if(!saving.value)done()}
watch(visible,async value=>{const id=++sequence;if(!value){pauseDraft();return}loading.value=true;error.value='';settings.value={};departments.value={};selected.value=[];keyword.value='';search.value='';onlyFixed.value=false;batchDepartment.value='';batchShift.value='';try{const data=await getFixedShiftConfig();if(id!==sequence)return;config.value=data;people.value=data.people;const valid=new Set(people.value.map(person=>person.id));settings.value=Object.fromEntries(data.assignments.filter(item=>valid.has(item.user_id)).map(item=>[item.user_id,{...item}]));if(!data.ready)error.value='固定班次配置表尚未初始化';else await beginDraft(`configuration:${data.revision}`)}catch(e){if(id===sequence)error.value=e.detail||'读取固定班次失败，请关闭后重试'}finally{if(id===sequence)loading.value=false}})
async function save(){saving.value=true;try{await saveFixedShiftConfig({revision:config.value.revision,assignments:Object.values(settings.value)});clearDraft();ElMessage.success('固定班次已保存');emit('saved');visible.value=false}catch(e){ElMessage.error(e.detail||'保存失败，请重试')}finally{saving.value=false}}
onBeforeUnmount(()=>{clearTimeout(timer);sequence++})
</script>
<style scoped>
.fixed-filter{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}.fixed-filter .el-input{width:300px;max-width:100%}.fixed-filter span,.fixed-note,small{color:#64748b;font-size:12px}.fixed-batch .el-select{width:180px}.fixed-batch{display:flex;align-items:baseline;flex-wrap:wrap;gap:8px}.fixed-batch :deep(.el-form-item){margin-right:0}.fixed-note{line-height:1.7}
</style>
<style>.fixed-shift-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.fixed-shift-dialog>.el-dialog__header,.fixed-shift-dialog>.el-dialog__footer{flex-shrink:0}.fixed-shift-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.fixed-shift-dialog>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc;padding:14px 20px}</style>
