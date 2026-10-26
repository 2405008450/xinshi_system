<template>
  <section v-loading="loading">
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-alert v-if="data && !data.membershipReady" title="跨部门成员功能待数据库初始化，当前显示现有部门人员。" type="warning" :closable="false" />
    <div class="roster-tools">
      <el-select v-if="!departmentName" v-model="selectedId" filterable placeholder="选择部门" @change="keyword=''"><el-option v-for="dept in data?.items || []" :key="dept.id" :value="dept.id" :label="`${dept.name}（${dept.userCount}人）`" /></el-select>
      <strong v-else>{{ selected?.name || departmentName }}</strong>
      <el-button type="primary" :icon="Plus" :disabled="!canEdit" @click="edit('add')">添加人员</el-button>
      <el-button type="danger" plain :icon="Minus" :disabled="!canEdit || !members.length" @click="edit('remove')">移出人员</el-button>
      <el-button :disabled="!canEdit || !members.length" @click="edit('positions')">调整职务</el-button>
    </div>
    <p v-if="data && !data.canManage">当前账号可查看名册；人员增减与职务调整由部门管理员操作。</p>
    <div class="roster-tools"><el-input v-model="keyword" clearable placeholder="搜索姓名、账号、职务、部门" @keyup.enter="applySearch" /><el-button @click="applySearch">查询</el-button></div>
    <el-table :data="filtered" border max-height="480">
      <el-table-column label="姓名" min-width="130"><template #default="{row}">{{ row.name }} <el-tag v-if="row.departments.length>1" type="warning" size="small">跨部门 {{ row.departments.length }}</el-tag><el-tag v-if="!row.active" type="info" size="small">已停用</el-tag></template></el-table-column>
      <el-table-column label="本部门职务" min-width="130"><template #default="{row}">{{ position(row) || '成员' }}</template></el-table-column>
      <el-table-column label="所属全部部门" min-width="220"><template #default="{row}"><div class="department-tags"><el-tag v-for="dept in row.departments" :key="dept.id" :type="dept.name===row.primaryDepartment ? 'primary' : 'info'" size="small">{{ dept.name }}{{ dept.position ? ` · ${dept.position}` : '' }}{{ dept.name===row.primaryDepartment ? '（主）' : '' }}</el-tag></div></template></el-table-column>
    </el-table>
    <DraggableFormDialog v-model="visible" :title="`${editingName} · ${modeTitle}`" class="department-roster-editor" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="!saving" :before-close="beforeClose">
      <p>从全公司在用人员中添加，可多选、按姓名或账号搜索；移出仅解除本部门归属。部门职务不会改变系统操作权限。</p>
      <div v-if="mode === 'add'" class="roster-tools">
        <el-select v-model="adding" multiple filterable clearable collapse-tags collapse-tags-tooltip aria-label="从全公司选择添加人员" placeholder="从全公司人员选择（可多选）" :disabled="saving" style="flex:1;min-width:0"><el-option v-for="person in available" :key="person.id" :label="personLabel(person)" :value="person.id" /></el-select>
        <el-button type="primary" :disabled="saving || !adding.length" @click="add">添加所选</el-button>
      </div>
      <div v-if="mode === 'remove'" class="roster-tools">
        <el-select v-model="removing" multiple filterable clearable collapse-tags collapse-tags-tooltip aria-label="选择移出人员" placeholder="选择要移出的本部门人员（可多选）" :disabled="saving" style="flex:1;min-width:0"><el-option v-for="row in draft" :key="row.user_id" :label="personLabel(person(row.user_id))" :value="row.user_id" /></el-select>
        <el-button type="danger" plain :disabled="saving || !removing.length" @click="remove">移出所选</el-button>
      </div>
      <el-table :data="draft" border>
        <el-table-column label="姓名" min-width="130"><template #default="{row}">{{ personName(row.user_id) }}</template></el-table-column>
        <el-table-column label="部门内职务" min-width="190"><template #default="{row}"><el-select v-if="mode !== 'remove'" v-model="row.position" :disabled="saving" filterable allow-create default-first-option clearable maxlength="50"><el-option v-for="value in positions" :key="value" :label="value" :value="value" /></el-select><span v-else>{{ row.position || '成员' }}</span></template></el-table-column>
      </el-table>
      <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><span class="roster-count">名册共 {{ draft.length }} 人{{ adding.length ? `，待添加 ${adding.length} 人` : removing.length ? `，待移出 ${removing.length} 人` : '' }}</span><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="conflict" @click="save">保存名册</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Minus } from '@element-plus/icons-vue'
import api from '@/api'
import { matchesSearch } from '@/utils/searchMatching'
import { applyDepartmentCatalog } from '@/constants/departments'
import { subscribe } from '@/utils/realtimeSocket'
import DraggableFormDialog from './DraggableFormDialog.vue'
const props=defineProps({departmentName:{type:String,default:''}})
const data=ref(null),loading=ref(false),error=ref(''),selectedId=ref(''),keyword=ref(''),applied=ref('')
const visible=ref(false),draft=ref([]),adding=ref([]),removing=ref([]),saving=ref(false),saveError=ref(''),revision=ref(0)
const mode=ref('add'),editingId=ref(''),editingName=ref(''),conflict=ref(false)
const modeTitle=computed(()=>({add:'添加人员',remove:'移出人员',positions:'调整职务'})[mode.value])
const canEdit=computed(()=>Boolean(data.value?.canManage && data.value.membershipReady && selected.value))
const positions=['客户经理','高级项目经理','资源经理','资源专员','项目经理','项目助理']
const selected=computed(()=>data.value?.items.find(d=>props.departmentName ? d.name===props.departmentName : d.id===selectedId.value))
const members=computed(()=>(data.value?.people.filter(person=>person.departments.some(d=>d.id===selected.value?.id))||[]).sort((a,b)=>{const rank=p=>{const i=positions.indexOf(position(p));return i<0?positions.length:i};return rank(a)-rank(b)||a.name.localeCompare(b.name,'zh-CN')}))
const position=person=>person.departments.find(d=>d.id===selected.value?.id)?.position||''
const filtered=computed(()=>members.value.filter(p=>matchesSearch([p.name,p.username,position(p),...p.departments.map(d=>d.name)].join(' '),applied.value)))
const available=computed(()=>data.value?.people.filter(p=>p.active&&!draft.value.some(d=>d.user_id===p.id))||[])
let timer,unsubscribe,sequence=0,controller
function applySearch(){clearTimeout(timer);applied.value=keyword.value.trim()}
watch(keyword,value=>{clearTimeout(timer);if(!value)applySearch();else timer=setTimeout(applySearch,400)})
async function load(){const seq=++sequence;controller?.abort();controller=new AbortController();loading.value=true;error.value='';try{const result=await api.get('/departments/organization',{signal:controller.signal});if(seq!==sequence)return;data.value=result;applyDepartmentCatalog(result);if(!selectedId.value)selectedId.value=result.items[0]?.id||''}catch(e){if(seq===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'组织架构加载失败'}finally{if(seq===sequence)loading.value=false}}
function edit(action='add'){if(!canEdit.value)return;mode.value=action;editingId.value=selected.value.id;editingName.value=selected.value.name;revision.value=selected.value.revision;draft.value=members.value.map(p=>({user_id:p.id,position:position(p)}));adding.value=[];removing.value=[];conflict.value=false;saveError.value='';visible.value=true}
function add(){const ids=new Set(available.value.map(p=>p.id));draft.value.push(...adding.value.filter(id=>ids.has(id)).map(id=>({user_id:id,position:''})));adding.value=[]}
function remove(){const ids=new Set(removing.value);draft.value=draft.value.filter(row=>!ids.has(row.user_id));removing.value=[]}
function person(id){return data.value?.people.find(p=>p.id===id)}
function personLabel(value){return value ? `${value.name}（${value.username}）${value.primaryDepartment ? ` · ${value.primaryDepartment}` : ''}` : '未知人员'}
function personName(id){return person(id)?.name||'未知人员'}
function beforeClose(done){if(!saving.value)done()}
async function save(){if(saving.value||conflict.value||!canEdit.value)return;add();remove();saving.value=true;saveError.value='';try{data.value=await api.put(`/departments/${editingId.value}/members`,{revision:revision.value,members:draft.value});applyDepartmentCatalog(data.value);visible.value=false;ElMessage.success('部门名册已同步')}catch(e){saveError.value=e.detail||e.message||'保存失败';if(e.response?.status===409){conflict.value=true;saveError.value='名册已被其他人修改，请取消后重新打开再调整';await load()}}finally{saving.value=false}}
onMounted(()=>{load();unsubscribe=subscribe('departments_changed',load)})
onBeforeUnmount(()=>{sequence++;controller?.abort();clearTimeout(timer);unsubscribe?.()})
defineExpose({load})
</script>
<style scoped>
.roster-tools{display:flex;align-items:center;gap:12px;margin:14px 0;flex-wrap:wrap}.roster-tools>.el-input{flex:1;min-width:180px}.department-tags{display:flex;flex-wrap:wrap;gap:6px}p{font-size:13px;color:#64748b;line-height:1.6}
.roster-count{margin-right:auto;color:var(--el-text-color-secondary);font-size:13px}
</style>
<style>
.department-roster-dialog,.department-roster-editor{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.department-roster-dialog>.el-dialog__header,.department-roster-dialog>.el-dialog__footer,.department-roster-editor>.el-dialog__header,.department-roster-editor>.el-dialog__footer{flex:none}.department-roster-dialog>.el-dialog__body,.department-roster-editor>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.department-roster-editor>.el-dialog__footer{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.department-roster-dialog>.el-dialog__footer,.department-roster-editor>.el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:#f8fafc}
</style>
