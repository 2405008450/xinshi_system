<template>
  <section class="department-page">
    <header><h2>部门管理</h2><el-button type="primary" :disabled="!ready || !allowed" @click="edit()">新增部门</el-button></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-alert v-else-if="!ready" title="部门目录尚未初始化，完成数据库同步后可新增和编辑" type="warning" :closable="false" />
    <p>部门改名会同步关联人员、排班和各处部门选项。行政部、ethan、jimmy 和超级管理员可调整部门、人员归属和职务。</p>
    <div class="department-search"><el-input v-model="keyword" clearable placeholder="搜索部门名称" @keyup.enter="query" /><el-button @click="query">查询</el-button><el-button @click="keyword='';query()">重置</el-button></div>
    <el-table :data="filtered" v-loading="loading" border><el-table-column type="index" label="序号" width="70" /><el-table-column prop="name" label="部门名称" /><el-table-column prop="userCount" label="关联人数" width="110" /><el-table-column label="操作" width="200" fixed="right"><template #default="{row}"><el-button link type="primary" @click="rosterName=row.name;rosterVisible=true">人员 / 职务</el-button><el-button link type="primary" :disabled="!ready || !allowed" @click="edit(row)">编辑名称</el-button></template></el-table-column></el-table>
    <DraggableFormDialog v-model="rosterVisible" :title="rosterName" class="department-roster-dialog" width="min(1000px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @closed="load"><DepartmentRoster :department-name="rosterName" /><template #footer><el-button @click="rosterVisible=false">关闭</el-button></template></DraggableFormDialog>
    <DraggableFormDialog v-model="visible" :title="current ? '编辑部门' : '新增部门'" width="min(520px, calc(100vw - 32px))" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" top="8vh" destroy-on-close>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item label="部门名称" prop="name"><el-input v-model="form.name" maxlength="50" show-word-limit @keyup.enter="save" /></el-form-item></AppForm>
      <p v-if="current">改名后原部门的人员归属和排班关联将一并更新。</p><el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { refreshDepartments } from '@/composables/useDepartmentCatalog'
import { applyDepartmentCatalog } from '@/constants/departments'
import { matchesSearch } from '@/utils/searchMatching'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DepartmentRoster from '@/components/common/DepartmentRoster.vue'
import { subscribe } from '@/utils/realtimeSocket'
const rosterVisible=ref(false),rosterName=ref('')
const items=ref([]),ready=ref(false),allowed=ref(false),loading=ref(false),error=ref(''),keyword=ref(''),applied=ref('')
const visible=ref(false),current=ref(null),saving=ref(false),saveError=ref(''),formRef=ref(),form=reactive({name:''})
const rules={name:[{required:true,whitespace:true,message:'请输入部门名称',trigger:'blur'},{max:50,message:'部门名称最多50个字符',trigger:'blur'}]}
const filtered=computed(()=>items.value.filter(row=>matchesSearch(row.name,applied.value)))
let timer,unsubscribe
function query(){clearTimeout(timer);applied.value=keyword.value.trim()}
watch(keyword,value=>{clearTimeout(timer);if(!value)query();else timer=setTimeout(query,400)})
async function load(){loading.value=true;error.value='';try{const data=await refreshDepartments();items.value=data.items;ready.value=data.ready;allowed.value=data.canManage}catch(e){error.value=e.detail||e.message||'部门加载失败'}finally{loading.value=false}}
function edit(row=null){current.value=row;form.name=row?.name||'';saveError.value='';visible.value=true}
async function save(){
  if(saving.value||!await formRef.value.validate().catch(()=>false))return
  saving.value=true;saveError.value=''
  try{const data=await api.request({url:current.value?`/departments/${current.value.id}`:'/departments',method:current.value?'put':'post',data:{name:form.name.trim(),revision:current.value?.revision}});applyDepartmentCatalog(data);items.value=data.items;visible.value=false;ElMessage.success('部门已保存，关联部门信息已同步')}
  catch(e){saveError.value=e.detail||e.message||'保存失败';if(e.response?.status===409){await load();current.value=items.value.find(row=>row.id===current.value?.id)||current.value}}
  finally{saving.value=false}
}
onMounted(()=>{load();unsubscribe=subscribe('departments_changed',load)})
onBeforeUnmount(()=>{clearTimeout(timer);unsubscribe?.()})
</script>
<style scoped>
.department-page{padding:20px;background:#fff;border-radius:10px}.department-page header{display:flex;align-items:center;justify-content:space-between;gap:12px}.department-page p{font-size:12px;color:#64748b;line-height:1.7}.department-search{display:flex;gap:8px;max-width:560px;margin:16px 0}.department-search .el-input{flex:1;min-width:0}
</style>
