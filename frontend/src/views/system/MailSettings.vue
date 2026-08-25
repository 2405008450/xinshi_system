<template>
  <el-card class="mail-settings-card">
    <template #header>
      <div class="page-header"><div><h2>项目邮件设置</h2><p>邮件组成员来自启用且已绑定邮箱的系统用户。</p></div><el-button v-if="canWrite" type="primary" @click="openGroup()">新增邮件组</el-button></div>
    </template>
    <el-alert :title="mailStatus.detail || '正在读取 SMTP 状态'" :type="mailStatus.configured ? (mailStatus.mode === 'test' ? 'warning' : 'success') : 'error'" :closable="false" show-icon />
    <el-tabs v-model="activeTab" class="settings-tabs">
      <el-tab-pane label="邮件组" name="groups">
        <el-table :data="groups" v-loading="loading" border>
          <el-table-column prop="name" label="组名" min-width="150" />
          <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
          <el-table-column label="成员" min-width="320"><template #default="{ row }"><el-tag v-for="item in row.members" :key="item.user_id" class="member-tag">{{ item.display_name }} · {{ item.email }}</el-tag></template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag></template></el-table-column>
          <el-table-column v-if="canWrite" label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openGroup(row)">编辑</el-button><el-button link type="danger" @click="removeGroup(row)">删除</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="项目默认收件组" name="policies">
        <el-form label-width="110px" class="policy-form">
          <section v-for="item in projectTypes" :key="item.value" class="policy-section">
            <h3>{{ item.label }}</h3>
            <el-form-item label="收件组"><el-select v-model="policies[item.value].to_group_ids" multiple filterable style="width:100%"><el-option v-for="group in activeGroups" :key="group.id" :label="group.name" :value="group.id" /></el-select></el-form-item>
            <el-form-item label="抄送组"><el-select v-model="policies[item.value].cc_group_ids" multiple filterable style="width:100%"><el-option v-for="group in activeGroups" :key="group.id" :label="group.name" :value="group.id" /></el-select></el-form-item>
            <el-button v-if="canWrite" type="primary" plain @click="savePolicy(item.value)">保存{{ item.label }}策略</el-button>
          </section>
        </el-form>
      </el-tab-pane>
    </el-tabs>
    <el-dialog v-model="groupDialog" :title="groupForm.id ? '编辑邮件组' : '新增邮件组'" width="min(680px, calc(100vw - 32px))">
      <el-form label-width="90px">
        <el-form-item label="组名" required><el-input v-model="groupForm.name" maxlength="100" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="groupForm.description" maxlength="500" /></el-form-item>
        <el-form-item label="成员" required><el-select v-model="groupForm.user_ids" multiple filterable collapse-tags collapse-tags-tooltip style="width:100%"><el-option v-for="user in validUsers" :key="user.id" :label="`${user.full_name || user.username} · ${user.email}`" :value="user.id" /></el-select></el-form-item>
        <el-form-item label="启用"><el-switch v-model="groupForm.is_active" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="groupDialog=false">取消</el-button><el-button type="primary" @click="saveGroup">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as mailApi from '@/api/businessMails'
import * as userApi from '@/api/users'
import { hasPermission } from '@/utils/permission'

const canWrite = hasPermission('system:mail_settings:write')
const loading = ref(false); const activeTab = ref('groups'); const groupDialog = ref(false)
const groups = ref([]); const users = ref([]); const mailStatus = reactive({})
const projectTypes = [{value:'translation',label:'笔译项目'},{value:'interpretation',label:'口译项目'},{value:'annotation',label:'标注项目'},{value:'recruitment',label:'招聘项目'}]
const policies = reactive(Object.fromEntries(projectTypes.map((item)=>[item.value,{to_group_ids:[],cc_group_ids:[]}])) )
const groupForm = reactive({id:'',name:'',description:'',is_active:true,user_ids:[]})
const validUsers = computed(()=>users.value.filter((item)=>item.is_active && item.email))
const activeGroups = computed(()=>groups.value.filter((item)=>item.is_active))

const load = async()=>{ loading.value=true; try { const [status,groupRows,userRows,...policyRows]=await Promise.all([mailApi.getMailStatus(),mailApi.getMailGroups(),userApi.getUsers({skip:0,limit:1000}),...projectTypes.map((item)=>mailApi.getMailPolicy(item.value))]); Object.assign(mailStatus,status); groups.value=groupRows; users.value=userRows; policyRows.forEach((row,index)=>Object.assign(policies[projectTypes[index].value],{to_group_ids:row.to_group_ids,cc_group_ids:row.cc_group_ids})) } catch(error){ElMessage.error(error.detail||'加载邮件设置失败')} finally{loading.value=false} }
const openGroup=(row=null)=>{Object.assign(groupForm,row?{id:row.id,name:row.name,description:row.description||'',is_active:row.is_active,user_ids:[...row.user_ids]}:{id:'',name:'',description:'',is_active:true,user_ids:[]});groupDialog.value=true}
const saveGroup=async()=>{if(!groupForm.name.trim()||!groupForm.user_ids.length)return ElMessage.warning('请填写组名并选择成员');try{const payload={name:groupForm.name.trim(),description:groupForm.description.trim()||null,is_active:groupForm.is_active,user_ids:groupForm.user_ids};if(groupForm.id)await mailApi.updateMailGroup(groupForm.id,payload);else await mailApi.createMailGroup(payload);groupDialog.value=false;ElMessage.success('邮件组已保存');await load()}catch(error){ElMessage.error(error.detail||'保存失败')}}
const removeGroup=async(row)=>{try{await ElMessageBox.confirm(`确认删除邮件组“${row.name}”吗？`,'提示',{type:'warning'});await mailApi.deleteMailGroup(row.id);ElMessage.success('已删除');await load()}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error.detail||'删除失败')}}
const savePolicy=async(type)=>{try{await mailApi.updateMailPolicy(type,policies[type]);ElMessage.success('项目邮件策略已保存')}catch(error){ElMessage.error(error.detail||'保存策略失败')}}
onMounted(load)
</script>

<style scoped>
.page-header{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-header h2{margin:0}.page-header p{margin:6px 0 0;color:var(--el-text-color-secondary)}.settings-tabs{margin-top:18px}.member-tag{margin:2px 6px 2px 0}.policy-form{max-width:860px}.policy-section{margin-bottom:18px;padding:16px;border:1px solid var(--el-border-color-lighter);border-radius:8px}.policy-section h3{margin:0 0 14px}
</style>
