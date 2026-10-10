<template>
  <DraggableFormDialog v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="development-dialog arrangement-editor" destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${form.work_date} · 每日安排`" placeholder="搜索字段，如负责人、岗位目标" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <el-alert v-if="form.carried_from" :title="`已沿用 ${form.carried_from} 的安排，保存后生效`" type="info" :closable="false" />
      <el-alert v-for="warning in warnings" :key="warning" :title="warning" type="warning" :closable="false" />
      <el-alert v-if="conflict" title="服务器记录已变化，当前草稿已保留。可重新加载后编辑，或先复制需要保留的内容。" type="warning" :closable="false"><el-button text @click="reloadDraft">重新加载</el-button></el-alert>
      <AppForm ref="formRef" :model="form" label-position="top">
        <section v-for="(cell, index) in form.cells" :key="cell.platform_id" class="arrangement-edit-cell" data-dialog-field-search-group>
          <h3 data-dialog-field-search-group-title>{{ cell.platform_name }}</h3>
          <el-form-item label="平台情况说明" :prop="`cells.${index}.platform_description`">
            <ReadonlyField :model-value="platformDescription(cell.platform_id)" source="auto" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="平台尚未填写情况说明" />
            <small class="muted"><el-icon><MagicStick /></el-icon> 从平台情况说明自动带出（只读），可记录年付情况、赠送额度及使用规则。</small>
          </el-form-item>
          <el-form-item label="负责人" :prop="`cells.${index}.owner_id`">
            <el-select v-model="cell.owner_id" clearable filterable :disabled="!options.can_delegate" placeholder="暂未分配">
              <el-option v-for="person in ownerOptions(cell)" :key="person.id" :label="person.name" :value="person.id" :disabled="person.inactive" />
            </el-select>
          </el-form-item>
          <el-form-item label="开拓方向（语种／方言）" :prop="`cells.${index}.targets`">
            <el-select :model-value="cell.targets.map(arrangementTargetKey)" multiple filterable :loading="targetsLoading" placeholder="选择已发送需求、自选语种或内部招聘" @update:model-value="keys => setTargets(cell, keys)" @visible-change="opened => opened && refreshTargets().catch(() => {})">
              <el-option-group label="已发送需求"><el-option v-for="target in requestOptions(cell)" :key="arrangementTargetKey(target)" :value="arrangementTargetKey(target)" :label="targetLabel(target)" :disabled="target.active === false" /></el-option-group>
              <el-option-group label="自选语种／方言"><el-option v-for="language in languageOptions(cell)" :key="language.id" :value="arrangementTargetKey({kind:'manual',language_id:language.id})" :label="`${language.label}（自选${language.inactive ? '，已停用' : ''}）`" :disabled="language.inactive" /></el-option-group>
              <el-option-group label="其他"><el-option label="内部招聘" :value="'internal::'" /></el-option-group>
            </el-select>
            <small v-if="cell.targets.some(t => t.active === false)" class="arrangement-warning">已有失效方向保留供追溯，也可以手动取消选择。</small>
          </el-form-item>
          <el-form-item label="岗位目标" :prop="`cells.${index}.role_tags`" :rules="roleRules">
            <el-select v-model="cell.role_tags" multiple filterable allow-create default-first-option clearable :reserve-keyword="false" placeholder="输入岗位后回车添加，如 HR、客服、译员">
              <el-option v-for="role in cell.role_tags" :key="role" :label="role" :value="role" />
            </el-select>
            <small class="muted">岗位与语种可分别填写；本账号当天的全部目标统一确认完成。</small>
          </el-form-item>
          <div class="arrangement-auto-projects" data-dialog-field-search-label="需求关联项目"><span>需求关联项目：</span><DevelopmentArrangementProject v-for="project in automaticProjects(cell)" :key="arrangementProjectKey(project)" :project="project" /><span v-if="!automaticProjects(cell).length">-</span></div>
          <el-form-item label="手动关联项目" :prop="`cells.${index}.manual_projects`">
            <div class="arrangement-project-selector">
              <el-select v-model="projectType" aria-label="项目类型" @change="searchProjects('')"><el-option v-for="type in arrangementProjectTypes" :key="type.value" :label="type.label" :value="type.value" /></el-select>
              <el-select :model-value="null" remote filterable clearable :remote-method="searchProjects" :loading="projectsLoading" placeholder="搜索订单号、项目名称，选择后添加" @update:model-value="key => addProject(cell, key)" @visible-change="opened => opened && searchProjects('')"><el-option v-for="project in projectOptions" :key="arrangementProjectKey(project)" :value="arrangementProjectKey(project)" :label="`${project.order_no} · ${project.project_name}`" /></el-select>
            </div>
            <div class="arrangement-project-tags"><el-tag v-for="project in cell.manual_projects" :key="arrangementProjectKey(project)" closable @close="cell.manual_projects = cell.manual_projects.filter(p => arrangementProjectKey(p) !== arrangementProjectKey(project))">{{ project.order_no || project.project_name }}</el-tag></div>
          </el-form-item>
          <el-form-item label="账号备注" :prop="`cells.${index}.remarks`"><el-input v-model="cell.remarks" type="textarea" :rows="3" maxlength="20000" /></el-form-item>
        </section>
        <el-form-item v-if="wholeDay && options.can_delegate" label="每日备注" prop="remarks"><el-input v-model="form.remarks" type="textarea" :rows="3" maxlength="20000" /></el-form-item>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="beforeClose(() => visible = false)">取消</el-button><el-button type="primary" :loading="saving" :disabled="conflict" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { arrangementCellChanged, arrangementCellPayload, arrangementProjectKey, arrangementProjectTypes, arrangementTargetKey, normalizeArrangementRoles } from '@/utils/resourceArrangements'
import DevelopmentArrangementProject from './DevelopmentArrangementProject.vue'
const props = defineProps({ options: { type: Object, required: true } }), emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), conflict = ref(false), wholeDay = ref(false), warnings = ref([])
const bodyRef = ref(), formRef = ref(), requestTargets = ref([]), targetsLoading = ref(false)
const form = reactive({ work_date: '', revision: 0, remarks: '', cells: [], carried_from: null })
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const projectType = ref('annotation'), projectOptions = ref([]), projectsLoading = ref(false)
const platforms = computed(() => props.options.options.filter(o => o.kind === 'platform'))
const platformDescription = id => platforms.value.find(p => p.id === id)?.description || ''
const roleRules = [{ validator: (_rule, value, callback) => {
  const tags = normalizeArrangementRoles(value)
  callback(tags.length > 100 || tags.some(tag => [...tag].length > 100) ? new Error('岗位目标最多100项，每项最多100个字符') : undefined)
}, trigger: 'change' }]
let baseline = {}, originalDay, editingPlatform, targetController, projectController, targetSeq = 0, projectSeq = 0, openingSeq = 0
const clone = value => JSON.parse(JSON.stringify(value))
function ownerOptions(cell) { return props.options.users.some(p => p.id === cell.owner_id) || !cell.owner_id ? props.options.users : [...props.options.users, { id: cell.owner_id, name: `${cell.owner_name}（已停用）`, inactive: true }] }
function languageOptions(cell) { const map = new Map(props.options.languages.map(l => [l.id,l])); for (const t of cell.targets) if (t.kind === 'manual' && !map.has(t.language_id)) map.set(t.language_id,{id:t.language_id,label:t.label,inactive:true}); return [...map.values()] }
function requestOptions(cell) { const map = new Map(requestTargets.value.map(t => [arrangementTargetKey(t), t])); for (const t of cell.targets) if (t.kind === 'request' && !map.has(arrangementTargetKey(t))) map.set(arrangementTargetKey(t), { ...t, active: false, inactive_reason: t.inactive_reason || '需求已取消或语种已调整' }); return [...map.values()] }
function targetLabel(t) { return `${t.label} · ${t.project?.order_no || t.request_no} · ${t.project?.project_name || t.source_name || ''}${t.active === false ? `（${t.inactive_reason}）` : ''}` }
function setTargets(cell, keys) {
  const map = new Map([...cell.targets, ...requestTargets.value, ...props.options.languages.map(l => ({kind:'manual',language_id:l.id,label:l.label})), {kind:'internal',label:'内部招聘'}].map(t => [arrangementTargetKey(t), t]))
  cell.targets = keys.map(key => map.get(key)).filter(Boolean)
}
function automaticProjects(cell) { return [...new Map(cell.targets.filter(t => t.project).map(t => [arrangementProjectKey(t.project), t.project])).values()] }
async function refreshTargets() {
  targetController?.abort(); targetController = new AbortController(); const seq = ++targetSeq; targetsLoading.value = true
  try { const data = await api.arrangementOptions({}, targetController.signal); if (seq === targetSeq) requestTargets.value = data.targets }
  catch (e) { if (seq === targetSeq && e.code !== 'ERR_CANCELED') { ElMessage.error(e.message); throw e } }
  finally { if (seq === targetSeq) targetsLoading.value = false }
}
async function searchProjects(keyword) {
  projectController?.abort(); projectController = new AbortController(); const seq = ++projectSeq; projectsLoading.value = true
  try { const data = await api.arrangementOptions({ source_type: projectType.value, keyword: keyword || undefined }, projectController.signal); if (seq === projectSeq) projectOptions.value = data.projects }
  catch (e) { if (seq === projectSeq && e.code !== 'ERR_CANCELED') ElMessage.error(e.message) }
  finally { if (seq === projectSeq) projectsLoading.value = false }
}
function addProject(cell, key) { const project = projectOptions.value.find(p => arrangementProjectKey(p) === key); if (project && !cell.manual_projects.some(p => arrangementProjectKey(p) === key)) cell.manual_projects.push(clone(project)) }
function applyDay(day, platformId) {
  const byId = new Map(day.cells.map(c => [c.platform_id, c])), definitions = new Map(platforms.value.map(p => [p.id, p.name]))
  for (const c of day.cells) definitions.set(c.platform_id, c.platform_name)
  Object.assign(form, { work_date: day.work_date, revision: day.revision, remarks: day.remarks, carried_from: day.carried_from || null,
    cells: [...definitions].filter(([id]) => !platformId || id === platformId).map(([id, name]) => ({ ...clone(byId.get(id) || { platform_id:id, platform_name:name, owner_id:null, targets:[], manual_projects:[], remarks:'' }), role_tags:normalizeArrangementRoles(byId.get(id)?.role_tags) })) })
  wholeDay.value = !platformId; warnings.value = day.warnings || []; conflict.value = false
  baseline = clone(form); clearFieldSearch()
}
async function open(day, platformId) { if (saving.value) return; const seq = ++openingSeq; await refreshTargets(); if (seq !== openingSeq) return; originalDay = day; editingPlatform = platformId; applyDay(day, platformId); visible.value = true }
async function beforeClose(done) { if (saving.value) return; if (JSON.stringify(form) !== JSON.stringify(baseline)) { try { await ElMessageBox.confirm('当前修改尚未保存，是否放弃？', '关闭每日安排', { type:'warning', confirmButtonText:'放弃修改', cancelButtonText:'继续编辑' }) } catch { return } } done() }
async function reloadDraft() { try { await ElMessageBox.confirm('重新加载会丢弃当前草稿，是否继续？', '重新加载'); const day = await api.arrangement(form.work_date); originalDay = day; await refreshTargets(); applyDay(day, editingPlatform) } catch (e) { if (e?.message) ElMessage.error(e.message) } }
async function save() {
  if (saving.value || !await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    await refreshTargets()
    const previous = new Map(originalDay.cells.map(c => [c.platform_id, c]))
    const cells = form.cells.filter(c => form.carried_from || arrangementCellChanged(c, previous.get(c.platform_id))).map(arrangementCellPayload)
    const payload = { revision: form.revision, cells, ...(form.carried_from ? { carried_from:form.carried_from } : {}), ...(wholeDay.value && props.options.can_delegate ? { remarks:form.remarks } : {}) }
    const day = await api.saveArrangement(form.work_date, payload)
    visible.value = false; emit('saved', day); ElMessage.success('每日安排已保存')
  } catch (e) {
    await formRef.value?.applyServerErrors(e)
    if ((e.status === 409 || e.response?.status === 409) && /这一天|该日期|目标日期/.test(e.message)) conflict.value = true
    if (/岗位/.test(e.message)) await locateDialogFieldByLabel('岗位目标')
    else if (/所选需求|语种|方言/.test(e.message)) await locateDialogFieldByLabel('开拓方向')
    else if (/关联项目/.test(e.message)) await locateDialogFieldByLabel('手动关联项目')
    ElMessage.error(e.message)
  }
  finally { saving.value = false }
}
onBeforeUnmount(() => { openingSeq++; targetSeq++; projectSeq++; targetController?.abort(); projectController?.abort() })
defineExpose({ open })
</script>
<style>
.arrangement-edit-cell{border-bottom:1px solid var(--el-border-color-light);padding:0 0 16px;margin-bottom:16px}.arrangement-edit-cell .el-select{width:100%}.arrangement-edit-cell h3{margin:12px 0}.arrangement-project-selector{display:grid;grid-template-columns:180px minmax(0,1fr);gap:10px;width:100%}.arrangement-project-tags,.arrangement-auto-projects{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.arrangement-warning{color:var(--el-color-warning);display:block}.arrangement-editor .el-alert{margin:8px 0}.arrangement-project-link{white-space:normal;height:auto;text-align:left}
@media(max-width:600px){.arrangement-project-selector{grid-template-columns:1fr}}
</style>
