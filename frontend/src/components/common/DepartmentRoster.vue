<template>
  <section v-loading="loading">
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-alert v-if="data && !data.membershipReady" title="跨部门成员功能待数据库初始化，当前显示现有部门人员。" type="warning" :closable="false" />
    <div class="roster-tools">
      <el-select v-if="!departmentName" v-model="selectedId" filterable placeholder="选择部门" @change="keyword=''"><el-option v-for="dept in data?.items || []" :key="dept.id" :value="dept.id" :label="`${dept.name}（${dept.userCount}人）`" /></el-select>
      <strong v-else>{{ selected?.name || departmentName }}</strong>
      <el-button v-if="data?.canManage" :disabled="!selected || !data.membershipReady" @click="edit">增减人员 / 调整职务</el-button>
    </div>
    <div class="roster-tools"><el-input v-model="keyword" clearable placeholder="搜索姓名、账号、职务、部门" @keyup.enter="applySearch" /><el-button @click="applySearch">查询</el-button></div>
    <el-table :data="filtered" border max-height="480">
      <el-table-column label="姓名" min-width="130"><template #default="{row}">{{ row.name }} <el-tag v-if="row.departments.length>1" type="warning" size="small">跨部门 {{ row.departments.length }}</el-tag><el-tag v-if="!row.active" type="info" size="small">已停用</el-tag></template></el-table-column>
      <el-table-column label="本部门职务" min-width="130"><template #default="{row}">{{ position(row) || '成员' }}</template></el-table-column>
      <el-table-column label="所属全部部门" min-width="220"><template #default="{row}"><div class="department-tags"><el-tag v-for="dept in row.departments" :key="dept.id" :type="dept.name===row.primaryDepartment ? 'primary' : 'info'" size="small">{{ dept.name }}{{ dept.position ? ` · ${dept.position}` : '' }}{{ dept.name===row.primaryDepartment ? '（主）' : '' }}</el-tag></div></template></el-table-column>
    </el-table>
    <DraggableFormDialog v-model="visible" :title="`${selected?.name || ''} · 人员与职务`" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="!saving" :before-close="beforeClose">
      <p>可多选添加全体人员；在这里移出仅解除本部门归属。部门职务不会改变系统操作权限。</p>
      <div class="roster-tools"><el-select v-model="adding" multiple filterable collapse-tags collapse-tags-tooltip placeholder="从全体人员选择（可多选）" style="flex:1"><el-option v-for="person in available" :key="person.id" :label="`${person.name}（${person.username}）`" :value="person.id" /></el-select><el-button :disabled="!adding.length" @click="add">添加所选</el-button></div>
      <el-table :data="draft" border>
        <el-table-column label="姓名" min-width="130"><template #default="{row}">{{ personName(row.user_id) }}</template></el-table-column>
        <el-table-column label="部门内职务" min-width="190"><template #default="{row}"><el-select v-model="row.position" filterable allow-create default-first-option clearable maxlength="50"><el-option v-for="value in positions" :key="value" :label="value" :value="value" /></el-select></template></el-table-column>
        <el-table-column label="操作" width="80"><template #default="{row}"><el-button link type="danger" @click="draft=draft.filter(item=>item!==row)">移出</el-button></template></el-table-column>
      </el-table>
      <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><span>共 {{ draft.length }} 人</span><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存名册</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { matchesSearch } from '@/utils/searchMatching'
import { applyDepartmentCatalog } from '@/constants/departments'
import { subscribe } from '@/utils/realtimeSocket'
import DraggableFormDialog from './DraggableFormDialog.vue'
const props=defineProps({departmentName:{type:String,default:''}})
const data=ref(null),loading=ref(false),error=ref(''),selectedId=ref(''),keyword=ref(''),applied=ref('')
const visible=ref(false),draft=ref([]),adding=ref([]),saving=ref(false),saveError=ref(''),revision=ref(0)
const positions=['客户经理','高级项目经理','项目经理','项目助理']
const selected=computed(()=>data.value?.items.find(d=>props.departmentName ? d.name===props.departmentName : d.id===selectedId.value))
const members=computed(()=>(data.value?.people.filter(person=>person.departments.some(d=>d.id===selected.value?.id))||[]).sort((a,b)=>{const rank=p=>{const i=positions.indexOf(position(p));return i<0?positions.length:i};return rank(a)-rank(b)||a.name.localeCompare(b.name,'zh-CN')}))
const position=person=>person.departments.find(d=>d.id===selected.value?.id)?.position||''
const filtered=computed(()=>members.value.filter(p=>matchesSearch([p.name,p.username,position(p),...p.departments.map(d=>d.name)].join(' '),applied.value)))
const available=computed(()=>data.value?.people.filter(p=>p.active&&!draft.value.some(d=>d.user_id===p.id))||[])
let timer,unsubscribe,sequence=0,controller
function applySearch(){clearTimeout(timer);applied.value=keyword.value.trim()}
watch(keyword,value=>{clearTimeout(timer);if(!value)applySearch();else timer=setTimeout(applySearch,400)})
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const result=await api.get('/departments/organization',{signal:controller.signal});if(seq!==sequence)return;data.value=result;applyDepartmentCatalog(result);if(!selectedId.value)selectedId.value=result.items[0]?.id||''}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'组织架构加载失败'}finally{if(seq===sequence)loading.value=false}}
function edit(){revision.value=selected.value.revision;draft.value=members.value.map(p=>({user_id:p.id,position:position(p)}));adding.value=[];saveError.value='';visible.value=true}
function add(){draft.value.push(...adding.value.map(id=>({user_id:id,position:''})));adding.value=[]}
function personName(id){return data.value?.people.find(p=>p.id===id)?.name||'未知人员'}
function beforeClose(done){if(!saving.value)done()}
async function save(){if(saving.value)return;saving.value=true;saveError.value='';try{data.value=await api.put(`/departments/${selected.value.id}/members`,{revision:revision.value,members:draft.value});applyDepartmentCatalog(data.value);visible.value=false;ElMessage.success('部门名册已同步')}catch(e){saveError.value=e.detail||e.message||'保存失败';if(e.response?.status===409)await load()}finally{saving.value=false}}
onMounted(()=>{load();unsubscribe=subscribe('departments_changed',load)})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer);unsubscribe?.()})
defineExpose({load})
</script>
<style scoped>
.roster-tools{display:flex;align-items:center;gap:12px;margin:14px 0;flex-wrap:wrap}.roster-tools>.el-input{flex:1;min-width:180px}.department-tags{display:flex;flex-wrap:wrap;gap:6px}p{font-size:13px;color:#64748b;line-height:1.6}
</style>
