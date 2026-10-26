<template>
  <section class="report-settings" v-loading="loading">
    <header><div><h3>工作报告设置</h3><p>配置“谁可以查看谁的工作报告”。同一规则内范围合并，多条规则分别生效。</p></div><el-button type="primary" :disabled="!catalog.ready || saving" @click="edit()">新增匹配规则</el-button></header>
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
    <el-alert v-else-if="!loading&&!catalog.ready" title="工作报告设置尚未初始化，完成数据库初始化后可保存规则。" type="warning" :closable="false" />
    <el-alert title="报告确认后，有权查看人可在工作台的“查看工作报告”中查看。部门范围随组织名册变化，草稿不对其他人开放。" type="info" :closable="false" />

    <div v-if="editing" class="rule-editor">
      <h4>{{ currentId ? '编辑匹配规则' : '新增匹配规则' }}</h4>
      <AppForm ref="formRef" :model="draft" :rules="rules" label-position="top" :disabled="saving || !catalog.ready">
        <el-form-item label="规则名称" prop="name"><el-input v-model="draft.name" maxlength="100" placeholder="例如：管理层查看全体工作报告" /></el-form-item>
        <div class="scope-grid">
          <section class="scope-card">
            <h4>有权查看人</h4>
            <el-checkbox v-model="draft.viewers_all">全体人员</el-checkbox>
            <el-form-item label="指定查看人" prop="viewer_ids">
              <el-select v-model="draft.viewer_ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="4" :disabled="draft.viewers_all" placeholder="搜索姓名或账号，可多选" aria-label="有权查看人">
                <el-option v-for="person in catalog.people" :key="person.id" :value="person.id" :label="personLabel(person)" :disabled="person.id===catalog.configurator_id" />
              </el-select>
            </el-form-item>
            <el-button link type="primary" :disabled="draft.viewers_all" @click="addSuggested">加入预设查看人</el-button>
            <p class="scope-help">预设：Ethan、Thomas、少妃、Lulu、运坚、家铭、翠珍、宇琪、赵震锋。可搜索并增减其他查看人，赵震锋始终保留。</p>
          </section>
          <section class="scope-card">
            <h4>发送报告人</h4>
            <el-checkbox v-model="draft.senders_all">全体成员（包括未分配部门人员）</el-checkbox>
            <el-checkbox v-model="draft.all_departments" :disabled="draft.senders_all">全部部门</el-checkbox>
            <el-form-item label="指定部门" prop="department_ids">
              <el-select v-model="draft.department_ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="4" :disabled="draft.senders_all || draft.all_departments" placeholder="搜索并多选部门" aria-label="发送报告部门">
                <el-option v-for="department in catalog.departments" :key="department.id" :value="department.id" :label="department.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="指定人员" prop="sender_ids">
              <el-select v-model="draft.sender_ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="4" :disabled="draft.senders_all" placeholder="搜索姓名或账号，可跨部门多选" aria-label="发送报告人">
                <el-option v-for="person in catalog.people" :key="person.id" :value="person.id" :label="personLabel(person)" />
              </el-select>
            </el-form-item>
            <p class="scope-help">指定部门与指定人员合并计算，跨部门人员自动去重。“全部部门”不包含未分配部门人员。</p>
          </section>
        </div>
        <div class="rule-preview">本条规则：{{ viewerCount }} 位查看人，可查看 {{ matchedSenders.length }} 位发送人的已确认工作报告。</div>
        <el-form-item label="规则状态"><el-switch v-model="draft.enabled" active-text="启用" inactive-text="停用" /></el-form-item>
      </AppForm>
      <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <div class="editor-actions"><el-button :disabled="saving" @click="editing=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!catalog.ready" @click="save">保存匹配规则</el-button></div>
    </div>

    <el-table :data="catalog.rules" border empty-text="尚未配置匹配规则，请新增规则">
      <el-table-column type="index" label="序号" width="65" />
      <el-table-column prop="name" label="规则名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="有权查看人" min-width="240"><template #default="{row}">{{ row.viewers_all ? '全体人员' : names(row.viewer_ids, catalog.people) }}</template></el-table-column>
      <el-table-column label="发送报告人" min-width="280"><template #default="{row}">{{ senderSummary(row) }}</template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{row}"><el-tag :type="row.enabled?'success':'info'">{{ row.enabled?'启用':'停用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button link type="primary" :disabled="saving" @click="edit(row)">编辑</el-button></template></el-table-column>
    </el-table>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getReportAccessSettings, createReportAccessRule, updateReportAccessRule } from '@/api/tasks'
import { reportScopePeople } from '@/utils/workReportAccess'

const catalog=reactive({ready:false,people:[],departments:[],rules:[],suggested_viewer_ids:[],configurator_id:''})
const loading=ref(false),saving=ref(false),loadError=ref(''),saveError=ref(''),editing=ref(false),currentId=ref(null),formRef=ref()
const draft=reactive({name:'',viewers_all:false,viewer_ids:[],senders_all:false,all_departments:false,department_ids:[],sender_ids:[],enabled:true,revision:null})
const matchedSenders=computed(()=>reportScopePeople(draft,catalog.people))
const viewerCount=computed(()=>draft.viewers_all?catalog.people.length:new Set(draft.viewer_ids).size)
const rules={
  name:[{required:true,whitespace:true,message:'请填写规则名称',trigger:'blur'}],
  viewer_ids:[{validator:(_rule,_value,done)=>done(!draft.viewers_all&&!draft.viewer_ids.length?new Error('请选择有权查看人'):undefined),trigger:'change'}],
  sender_ids:[{validator:(_rule,_value,done)=>done(!draft.senders_all&&!draft.all_departments&&!draft.department_ids.length&&!draft.sender_ids.length?new Error('请选择发送报告人或部门'):undefined),trigger:'change'}]
}
const personLabel=person=>`${person.name}（${person.username}）`
function names(ids,options){return ids.map(id=>options.find(option=>option.id===id)?.name||'已停用或移除').join('、')||'-'}
function senderSummary(row){if(row.senders_all)return '全体成员';return [row.all_departments?'全部部门':row.department_ids.length?`部门：${names(row.department_ids,catalog.departments)}`:'',row.sender_ids.length?`人员：${names(row.sender_ids,catalog.people)}`:''].filter(Boolean).join('；')}
function addSuggested(){draft.viewer_ids=[...new Set([...draft.viewer_ids,...catalog.suggested_viewer_ids,catalog.configurator_id])].filter(Boolean)}
function edit(row){currentId.value=row?.id||null;Object.assign(draft,{name:row?.name||'工作报告查看范围',viewers_all:row?.viewers_all||false,viewer_ids:row?[...row.viewer_ids]:[...catalog.suggested_viewer_ids],senders_all:row?.senders_all??true,all_departments:row?.all_departments||false,department_ids:[...(row?.department_ids||[])],sender_ids:[...(row?.sender_ids||[])],enabled:row?.enabled??true,revision:row?.revision||null});if(!draft.viewer_ids.includes(catalog.configurator_id))draft.viewer_ids.push(catalog.configurator_id);saveError.value='';editing.value=true;formRef.value?.clearValidate()}
async function load(){loading.value=true;loadError.value='';try{Object.assign(catalog,await getReportAccessSettings())}catch(error){loadError.value=error.detail||'读取工作报告设置失败'}finally{loading.value=false}}
async function save(){if(saving.value)return;try{await formRef.value.validate()}catch{return}saving.value=true;saveError.value='';try{const payload={...draft,viewer_ids:[...draft.viewer_ids],department_ids:[...draft.department_ids],sender_ids:[...draft.sender_ids]};const row=currentId.value?await updateReportAccessRule(currentId.value,payload):await createReportAccessRule(payload);catalog.rules=[row,...catalog.rules.filter(item=>item.id!==row.id)];editing.value=false;ElMessage.success('工作报告匹配规则已保存')}catch(error){saveError.value=error.detail||'保存失败，请重试'}finally{saving.value=false}}
onMounted(load)
</script>

<style scoped>
.report-settings{display:flex;flex-direction:column;gap:16px}.report-settings header{display:flex;align-items:center;justify-content:space-between;gap:16px}.report-settings h3,.report-settings h4{margin:0 0 10px}.report-settings p{margin:4px 0;color:#64748b;font-size:13px;line-height:1.6}.rule-editor{border:1px solid #dbe3ec;border-radius:8px;padding:20px;background:#fff}.scope-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.scope-card{border:1px solid #e2e8f0;border-radius:6px;padding:16px;min-width:0}.scope-card :deep(.el-select){width:100%}.scope-card :deep(.el-checkbox){display:flex;white-space:normal;height:auto;min-height:32px}.scope-card :deep(.el-checkbox__label){white-space:normal}.scope-help{font-size:12px!important}.rule-preview{padding:14px 0;color:#334155}.editor-actions{display:flex;justify-content:flex-end;gap:12px;border-top:1px solid #e2e8f0;margin-top:12px;padding-top:16px}@media(max-width:760px){.scope-grid{grid-template-columns:1fr}.report-settings header{align-items:flex-start;flex-direction:column}.rule-editor{padding:12px}}
</style>
