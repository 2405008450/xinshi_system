<template>
  <DraggableFormDialog v-model="visible" title="调整所属部门" class="user-department-dialog" width="min(600px, calc(100vw - 32px))" append-to-body destroy-on-close :before-close="done=>{if(!saving)done()}">
    <p>{{user?.full_name || user?.username}}（{{user?.username}}）</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" v-loading="loading">
      <el-form-item label="所属部门" prop="department_ids"><el-select v-model="form.department_ids" multiple filterable clearable placeholder="可多选；清空表示未分部门" style="width:100%" :disabled="saving||loading" @change="syncPrimary"><el-option v-for="department in departments" :key="department.id" :value="department.id" :label="department.name" /></el-select></el-form-item>
      <el-form-item v-if="form.department_ids.length" label="主部门" prop="primary_department_id"><el-select v-model="form.primary_department_id" style="width:100%" :disabled="saving||loading" placeholder="请选择主部门"><el-option v-for="department in selectedDepartments" :key="department.id" :value="department.id" :label="department.name" /></el-select></el-form-item>
    </AppForm>
    <p class="department-note">确认后同步更新部门名册；保留仍所属部门中的原职务。取消或关闭不保存。</p>
    <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||!loaded||conflict" @click="confirm">确认</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {getUserDepartmentDirectory,updateUserDepartments} from '@/api/users'
const props=defineProps({modelValue:Boolean,user:{type:Object,default:null}})
const emit=defineEmits(['update:modelValue','saved'])
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const form=reactive({department_ids:[],primary_department_id:null}),formRef=ref(),departments=ref([])
const loading=ref(false),saving=ref(false),error=ref(''),loaded=ref(false),conflict=ref(false)
let snapshot={},sequence=0
const selectedDepartments=computed(()=>departments.value.filter(d=>form.department_ids.includes(d.id)))
const rules={primary_department_id:[{validator:(_rule,value,done)=>done(form.department_ids.length&&!value?new Error('请选择主部门'):undefined),trigger:'change'}]}
function syncPrimary(){if(!form.department_ids.includes(form.primary_department_id))form.primary_department_id=form.department_ids[0]||null}
watch(()=>props.modelValue,async open=>{
  const id=++sequence;if(!open)return
  loading.value=true;loaded.value=false;error.value='';conflict.value=false
  try{
    const data=await getUserDepartmentDirectory();if(id!==sequence)return
    if(!data.canManage||!data.membershipReady)throw new Error('当前账号无部门管理权限或部门名册尚未就绪')
    const person=data.people.find(p=>p.id===props.user?.id);if(!person)throw new Error('人员不存在，请刷新后重试')
    departments.value=data.items
    form.department_ids=person.departments.map(d=>d.id)
    form.primary_department_id=person.departments.find(d=>d.name===person.primaryDepartment)?.id||form.department_ids[0]||null
    snapshot={expected_department_ids:[...form.department_ids],expected_primary_department:person.primaryDepartment||null,revisions:Object.fromEntries(data.items.map(d=>[d.id,d.revision]))}
    loaded.value=true
  }catch(e){if(id===sequence)error.value=e.detail||e.message||'读取部门失败'}finally{if(id===sequence)loading.value=false}
})
async function confirm(){
  if(saving.value||!loaded.value||conflict.value)return
  try{await formRef.value.validate()}catch{return}
  saving.value=true;error.value=''
  try{await updateUserDepartments(props.user.id,{...snapshot,department_ids:[...form.department_ids],primary_department_id:form.primary_department_id});visible.value=false;emit('saved');ElMessage.success('所属部门已更新')}
  catch(e){error.value=e.detail||e.message||'调整失败';if(e.response?.status===409)conflict.value=true}
  finally{saving.value=false}
}
</script>
<style scoped>.department-note{color:#64748b;font-size:13px;line-height:1.6}</style>
