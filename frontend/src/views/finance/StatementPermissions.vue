<template>
  <el-card v-loading="loading">
    <template #header><strong>对账单权限管理</strong></template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="allowed">
      <p>仅赵震锋可配置。内容修改权限允许修改客户账单内容；跨客户权限允许在已授权客户之间合并、分拆及调配。两项权限独立控制。</p>
      <AppForm :model="form" inline @submit.prevent="save">
        <el-form-item label="人员" prop="user_ids"><el-select v-model="form.user_ids" multiple clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="2" filterable style="width:280px;max-width:100%" @change="select"><el-option v-for="user in data.users" :key="user.id" :value="user.id" :label="`${user.name}（${user.username}）`" /></el-select></el-form-item>
        <el-form-item label="客户" prop="client_ids"><el-select v-model="form.client_ids" multiple clearable collapse-tags collapse-tags-tooltip :max-collapse-tags="2" filterable style="width:360px;max-width:100%" @change="select"><el-option v-for="client in data.clients" :key="client.id" :value="client.id" :label="`${client.name} ${client.code||''}`" /></el-select></el-form-item>
        <el-form-item><el-checkbox :model-value="form.edit_content===true" :indeterminate="form.edit_content===null" @update:model-value="form.edit_content=$event">允许修改内容</el-checkbox><el-checkbox :model-value="form.cross_client===true" :indeterminate="form.cross_client===null" @update:model-value="form.cross_client=$event">允许跨客户操作</el-checkbox></el-form-item>
        <el-form-item><el-button type="primary" :disabled="!pairCount||pairCount>5000||!data.ready||(form.edit_content===null&&form.cross_client===null)" :loading="saving" @click="save">保存授权并记录</el-button></el-form-item>
      </AppForm>
      <p v-if="pairCount">已选 {{form.user_ids.length}} 人、{{form.client_ids.length}} 个客户，共 {{pairCount}} 组授权。<template v-if="form.edit_content===null||form.cross_client===null">横线表示现有设置不一致；未点击的横线权限保持各组合原设置。</template></p>
      <el-table :data="data.grants" border><el-table-column label="人员"><template #default="{row}">{{userName(row.user_id)}}</template></el-table-column><el-table-column label="客户"><template #default="{row}">{{clientName(row.client_id)}}</template></el-table-column><el-table-column label="内容修改"><template #default="{row}">{{row.edit_content?'已授权':'无'}}</template></el-table-column><el-table-column label="跨客户操作"><template #default="{row}">{{row.cross_client?'已授权':'无'}}</template></el-table-column><el-table-column label="设置" width="100"><template #default="{row}"><el-button link @click="editRow(row)">调整</el-button></template></el-table-column></el-table>
      <h4>授权调整记录</h4><el-table :data="history" border max-height="400"><el-table-column label="人员"><template #default="{row}">{{userName(row.user_id)}}</template></el-table-column><el-table-column label="客户"><template #default="{row}">{{clientName(row.client_id)}}</template></el-table-column><el-table-column prop="actor_name" label="调整人" width="120" /><el-table-column label="调整时间" width="180"><template #default="{row}">{{formatBusinessDateTime(row.created_at)}}</template></el-table-column><el-table-column label="调整前／后" min-width="250"><template #default="{row}">内容修改：{{row.before.edit_content?'允许':'禁止'}} → {{row.after.edit_content?'允许':'禁止'}}；跨客户：{{row.before.cross_client?'允许':'禁止'}} → {{row.after.cross_client?'允许':'禁止'}}</template></el-table-column></el-table>
      <el-pagination v-model:current-page="historyPage" :page-size="20" :total="historyTotal" layout="total,prev,pager,next" @current-change="loadHistory" />
    </template>
  </el-card>
</template>
<script setup>
import {computed,onMounted,reactive,ref} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import {getStatementAccessConfiguration,getStatementGrantHistory,saveStatementGrantsBatch} from '@/api/statementAccess'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {formatBusinessDateTime} from '@/utils/dateTime'
const allowed=ref(false),loading=ref(false),saving=ref(false),error=ref(''),history=ref([]),data=ref({users:[],clients:[],grants:[]})
const historyPage=ref(1),historyTotal=ref(0)
const form=reactive({user_ids:[],client_ids:[],edit_content:false,cross_client:false})
const pairCount=computed(()=>form.user_ids.length*form.client_ids.length)
const grantMap=computed(()=>new Map(data.value.grants.map(row=>[`${row.user_id}:${row.client_id}`,row])))
const userName=id=>data.value.users.find(user=>user.id===id)?.name||id
const clientName=id=>data.value.clients.find(client=>client.id===id)?.name||id
function select(){for(const field of ['edit_content','cross_client']){const values=new Set(form.user_ids.flatMap(uid=>form.client_ids.map(cid=>!!grantMap.value.get(`${uid}:${cid}`)?.[field])));form[field]=values.size>1?null:values.has(true)}}
function editRow(row){form.user_ids=[row.user_id];form.client_ids=[row.client_id];select()}

async function loadHistory(){const result=await getStatementGrantHistory({skip:(historyPage.value-1)*20,limit:20});history.value=result.items||[];historyTotal.value=result.total||0}
async function load(){loading.value=true;try{data.value=await getStatementAccessConfiguration();allowed.value=true;await loadHistory()}catch(e){error.value=getLocalizedErrorMessage(e,'权限配置加载失败')}finally{loading.value=false}}
async function save(){
  const userIds=[...form.user_ids],clientIds=[...form.client_ids]
  const expected=userIds.flatMap(user_id=>clientIds.map(client_id=>({user_id,client_id,revision:grantMap.value.get(`${user_id}:${client_id}`)?.revision||0})))
  const payload={user_ids:userIds,client_ids:clientIds,expected,edit_content:form.edit_content,cross_client:form.cross_client}
  const label=value=>value===null?'保持各组合原设置':value?'允许':'禁止'
  try{await ElMessageBox.confirm(`将 ${userIds.map(userName).join('、')} 对所选 ${clientIds.length} 个客户的 ${expected.length} 组授权统一设置：内容修改${label(payload.edit_content)}；跨客户操作${label(payload.cross_client)}。每组均保留记录。`,'批量授权确认',{type:'warning',confirmButtonText:'确认保存',cancelButtonText:'取消'})}catch{return}
  saving.value=true;error.value=''
  try{const result=await saveStatementGrantsBatch(payload);historyPage.value=1;await load();select();ElMessage.success(`已保存 ${result.affected_count} 组授权并逐项记录`)}catch(e){error.value=getLocalizedErrorMessage(e,'批量授权保存失败')}finally{saving.value=false}
}

onMounted(load)
</script>
