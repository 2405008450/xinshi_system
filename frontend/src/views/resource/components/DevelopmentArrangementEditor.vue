<template>
  <DraggableFormDialog v-model="visible" width="min(960px, calc(100vw - 32px))" top="5vh" class="development-dialog arrangement-editor" destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="`${form.work_date} · 每日安排`" placeholder="搜索字段，如负责人、岗位目标" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <el-alert v-if="form.carried_from" :title="`已沿用 ${form.carried_from} 的安排，保存后生效`" type="info" :closable="false" />
      <el-alert v-for="warning in warnings" :key="warning" :title="warning" type="warning" :closable="false" />
      <el-alert v-if="conflict" title="服务器记录已变化，当前草稿已保留。可重新加载后编辑，或先复制需要保留的内容。" type="warning" :closable="false"><el-button text @click="reloadDraft">重新加载</el-button></el-alert>
      <AppForm ref="formRef" :model="form" label-position="top">
        <section v-for="group in editorGroups" :key="group.value" class="arrangement-edit-category">
          <h2>{{ group.label }}</h2>
          <p v-if="!group.platforms.length" class="muted">暂无平台</p>
          <section v-for="platform in group.platforms" :key="platform.id" class="arrangement-edit-platform">
            <h3>{{ platform.name }}</h3>
            <section v-for="{ cell, index, id, path } in platform.accounts" :key="id" class="arrangement-edit-cell" data-dialog-field-search-group>
              <h4 data-dialog-field-search-group-title>{{ path }}</h4>
              <el-form-item label="平台情况说明" :prop="`cells.${index}.platform_description`">
                <ReadonlyField :model-value="platformDescription(cell.platform_id)" source="auto" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="平台尚未填写情况说明" />
                <small class="muted"><el-icon><MagicStick /></el-icon> 从平台情况说明自动带出（只读），可记录年付情况、赠送额度及使用规则。</small>
              </el-form-item>
              <el-form-item label="负责人" :prop="`cells.${index}.owner_id`">
                <el-select v-model="cell.owner_id" clearable filterable :disabled="!options.can_write" placeholder="暂未分配">
                  <el-option v-for="person in ownerOptions(cell)" :key="person.id" :label="person.name" :value="person.id" :disabled="person.inactive" />
                </el-select>
              </el-form-item>
              <el-form-item label="开拓方向（语种／方言）" :prop="`cells.${index}.targets`">
                <el-select :model-value="cell.targets.map(arrangementTargetKey)" multiple filterable popper-class="arrangement-target-dropdown" :loading="targetsLoading" placeholder="选择需求确认的项目、自选语种或内部招聘" @update:model-value="keys => setTargets(cell, keys)" @visible-change="opened => targetDropdownChanged(opened, `${index}:targets`)">
                  <template #tag>
                    <el-tag v-for="target in cell.targets" :key="arrangementTargetKey(target)" :type="target.active === false ? 'warning' : 'info'" :closable="!saving" @close.stop="cell.targets = cell.targets.filter(item => arrangementTargetKey(item) !== arrangementTargetKey(target))">{{ target.kind === 'manual' ? `${target.label}（自选）` : arrangementTargetLabel(target) }}</el-tag>
                  </template>
                  <el-option-group label="需求确认"><el-option v-for="target in requestOptions()" :key="arrangementTargetKey(target)" :value="arrangementTargetKey(target)" :label="arrangementTargetLabel(target)" :disabled="target.active === false"><div class="arrangement-option-row"><span class="arrangement-option-title" :title="arrangementTargetLabel(target)">{{ arrangementTargetLabel(target) }}</span><el-button link type="primary" class="arrangement-option-more" :aria-label="`${arrangementTargetLabel(target)} 更多信息`" @mousedown.stop.prevent @click.stop="openOptionDetails(target, $event.currentTarget, `${index}:targets`)" @keydown.stop>更多信息</el-button></div></el-option></el-option-group>
                  <el-option-group label="自选语种／方言"><el-option v-for="language in languageOptions(cell)" :key="language.id" :value="arrangementTargetKey({kind:'manual',language_id:language.id})" :label="`${language.label}（自选${language.inactive ? '，已停用' : ''}）`" :disabled="language.inactive" /></el-option-group>
                  <el-option-group label="其他"><el-option label="内部招聘" :value="'internal::'" /></el-option-group>
                  <template #footer><ArrangementOptionDetails v-if="detailContext === `${index}:targets` && detailTarget" v-model="detailVisible" :anchor="detailAnchor" :target="detailTarget" :users="options.users" /></template>
                </el-select>
                <small class="muted">项目候选默认仅显示“需求确认”的需求。</small>
                <small v-if="cell.targets.some(t => t.active === false)" class="arrangement-warning">已有失效方向仅在已选项中保留，可点击标签 × 移除。</small>
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
                  <el-select :model-value="null" remote filterable clearable popper-class="arrangement-target-dropdown" :remote-method="queueProjectSearch" :debounce="0" :loading="projectsLoading" placeholder="搜索语种、项目名称或订单号，选择后添加" @update:model-value="key => addProject(cell, key)" @visible-change="opened => projectDropdownChanged(opened, `${index}:projects`)">
                    <el-option v-for="project in projectOptions" :key="arrangementProjectKey(project)" :value="arrangementProjectKey(project)" :label="projectOptionLabel(project)" class="arrangement-project-option">
                      <div class="arrangement-option-row">
                        <el-tag v-if="project.parent_project_id" size="small" type="info" class="arrangement-child-order-badge">子订单</el-tag>
                        <span class="arrangement-option-title" :title="project.project_name">{{ project.project_name || '未命名项目' }}</span>
                        <el-button link type="primary" class="arrangement-option-more" :aria-label="`${project.project_name} 更多信息`" @mousedown.stop.prevent @click.stop="openOptionDetails({ project }, $event.currentTarget, `${index}:projects`)" @keydown.stop>更多信息</el-button>
                      </div>
                      <div class="arrangement-project-languages">
                        <span class="arrangement-language-label">语种：</span>
                        <el-tag v-for="language in project.languages || []" :key="language" size="small" effect="plain">{{ language }}</el-tag>
                        <span v-if="!project.languages?.length" class="muted">未配置语种</span>
                      </div>
                    </el-option>
                    <template #footer><ArrangementOptionDetails v-if="detailContext === `${index}:projects` && detailTarget" v-model="detailVisible" :anchor="detailAnchor" :target="detailTarget" :users="options.users" /></template>
                  </el-select>
                </div>
                <div class="arrangement-project-tags"><el-tag v-for="project in cell.manual_projects" :key="arrangementProjectKey(project)" closable @close="cell.manual_projects = cell.manual_projects.filter(p => arrangementProjectKey(p) !== arrangementProjectKey(project))">{{ project.order_no || project.project_name }}</el-tag></div>
              </el-form-item>
              <el-form-item label="账号备注" :prop="`cells.${index}.remarks`"><el-input v-model="cell.remarks" type="textarea" :rows="3" maxlength="20000" /></el-form-item>
            </section>
          </section>
        </section>
        <el-form-item v-if="wholeDay && options.can_write" label="每日备注" prop="remarks"><el-input v-model="form.remarks" type="textarea" :rows="3" maxlength="20000" /></el-form-item>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="beforeClose(() => visible = false)">取消</el-button><el-button type="primary" :loading="saving" :disabled="conflict" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref, shallowRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { arrangementCellChanged, arrangementCellPayload, arrangementProjectKey, arrangementProjectTypes, arrangementTargetKey, arrangementTargetLabel, normalizeArrangementRoles, arrangementDefinitions, groupArrangementAccounts, arrangementTableRows } from '@/utils/resourceArrangements'
import DevelopmentArrangementProject from './DevelopmentArrangementProject.vue'
import ArrangementOptionDetails from './ArrangementOptionDetails.vue'
const props = defineProps({ options: { type: Object, required: true } }), emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), conflict = ref(false), wholeDay = ref(false), warnings = ref([])
const bodyRef = ref(), formRef = ref(), requestTargets = ref([]), targetsLoading = ref(false)
const form = reactive({ work_date: '', revision: 0, remarks: '', cells: [], carried_from: null })
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const projectType = ref('annotation'), projectOptions = ref([]), projectsLoading = ref(false), projectKeyword = ref('')
let projectSearchTimer
function queueProjectSearch(keyword) {
  projectKeyword.value = String(keyword || ''); clearTimeout(projectSearchTimer); projectController?.abort(); projectSeq++
  if (!projectKeyword.value) return searchProjects('')
  projectSearchTimer = setTimeout(() => searchProjects(projectKeyword.value), 400)
}
const projectOptionLabel = project => [project.project_name || '未命名项目', project.parent_project_id ? '子订单' : '', project.languages?.join('、') || '未配置语种'].filter(Boolean).join(' · ')
const detailVisible = ref(false), detailContext = ref(''), detailAnchor = shallowRef(), detailTarget = shallowRef(null)
function openOptionDetails(target, anchor, context) { detailVisible.value = false; detailContext.value = context; detailTarget.value = target; detailAnchor.value = anchor; detailVisible.value = true }
function closeOptionDetails(context) { if (detailContext.value === context) { detailVisible.value = false; detailTarget.value = null } }
function targetDropdownChanged(opened, context) { if (opened) refreshTargets().catch(() => {}); else closeOptionDetails(context) }
function projectDropdownChanged(opened, context) {
  if (opened) searchProjects(projectKeyword.value)
  else { clearTimeout(projectSearchTimer); projectController?.abort(); projectSeq++; projectsLoading.value = false; projectKeyword.value = ''; closeOptionDetails(context) }
}
const platforms = computed(() => arrangementDefinitions(props.options))
const editorGroups = computed(() => groupArrangementAccounts(props.options, form.cells, { includeUnarranged: false, includeEmpty: wholeDay.value }))
const platformDescription = id => platforms.value.find(p => p.id === id)?.description || ''
const roleRules = [{ validator: (_rule, value, callback) => {
  const tags = normalizeArrangementRoles(value)
  callback(tags.length > 100 || tags.some(tag => [...tag].length > 100) ? new Error('岗位目标最多100项，每项最多100个字符') : undefined)
}, trigger: 'change' }]
let baseline = {}, originalDay, editingPlatform, targetController, projectController, targetSeq = 0, projectSeq = 0, openingSeq = 0
const clone = value => JSON.parse(JSON.stringify(value))
function ownerOptions(cell) { return props.options.users.some(p => p.id === cell.owner_id) || !cell.owner_id ? props.options.users : [...props.options.users, { id: cell.owner_id, name: `${cell.owner_name}（已停用）`, inactive: true }] }
function languageOptions(cell) { const map = new Map(props.options.languages.map(l => [l.id,l])); for (const t of cell.targets) if (t.kind === 'manual' && !map.has(t.language_id)) map.set(t.language_id,{id:t.language_id,label:t.label,inactive:true}); return [...map.values()] }
function requestOptions() { return requestTargets.value.filter(t => t.active !== false && (!t.demand_status || t.demand_status === 'confirmed')) }
function setTargets(cell, keys) {
  const map = new Map([...cell.targets, ...requestTargets.value, ...props.options.languages.map(l => ({kind:'manual',language_id:l.id,label:l.label})), {kind:'internal',label:'内部招聘'}].map(t => [arrangementTargetKey(t), t]))
  cell.targets = keys.map(key => map.get(key)).filter(Boolean)
}
function automaticProjects(cell) { return [...new Map(cell.targets.filter(t => t.project).map(t => [arrangementProjectKey(t.project), t.project])).values()] }
async function refreshTargets() {
  targetController?.abort(); targetController = new AbortController(); const seq = ++targetSeq; targetsLoading.value = true
  try { const data = await api.arrangementOptions({}, targetController.signal); if (seq === targetSeq) requestTargets.value = [...data.targets, ...(data.request_projects || [])] }
  catch (e) { if (seq === targetSeq && e.code !== 'ERR_CANCELED') { ElMessage.error(e.message); throw e } }
  finally { if (seq === targetSeq) targetsLoading.value = false }
}
async function searchProjects(keyword) {
  clearTimeout(projectSearchTimer); projectKeyword.value = String(keyword || '')
  projectController?.abort(); projectController = new AbortController(); const seq = ++projectSeq; projectsLoading.value = true
  try { const data = await api.arrangementOptions({ source_type: projectType.value, keyword: keyword || undefined }, projectController.signal); if (seq === projectSeq) projectOptions.value = data.projects }
  catch (e) { if (seq === projectSeq && e.code !== 'ERR_CANCELED') ElMessage.error(e.message) }
  finally { if (seq === projectSeq) projectsLoading.value = false }
}
function addProject(cell, key) { const project = projectOptions.value.find(p => arrangementProjectKey(p) === key); if (project && !cell.manual_projects.some(p => arrangementProjectKey(p) === key)) cell.manual_projects.push(clone(project)) }
function applyDay(day, platformId) {
  detailVisible.value = false; detailTarget.value = null
  const accounts = arrangementTableRows(groupArrangementAccounts(props.options, day.cells, { includeEmpty: false }))
  Object.assign(form, { work_date: day.work_date, revision: day.revision, remarks: day.remarks, carried_from: day.carried_from || null,
    cells: accounts.filter(account => !account.placeholder && (!platformId || account.id === platformId)).map(account => ({ ...clone(account.cell || { platform_id:account.id, platform_name:account.name, owner_id:null, targets:[], manual_projects:[], remarks:'' }), role_tags:normalizeArrangementRoles(account.cell?.role_tags) })) })
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
    const payload = { revision: form.revision, cells, ...(form.carried_from ? { carried_from:form.carried_from } : {}), ...(wholeDay.value && props.options.can_write ? { remarks:form.remarks } : {}) }
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
onBeforeUnmount(() => { clearTimeout(projectSearchTimer); openingSeq++; targetSeq++; projectSeq++; targetController?.abort(); projectController?.abort() })
defineExpose({ open })
</script>
<style>
.arrangement-edit-cell{border-bottom:1px solid var(--el-border-color-light);padding:0 0 16px;margin-bottom:16px}.arrangement-edit-cell .el-select{width:100%}.arrangement-edit-cell h3{margin:12px 0}.arrangement-project-selector{display:grid;grid-template-columns:180px minmax(0,1fr);gap:10px;width:100%}.arrangement-project-tags,.arrangement-auto-projects{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.arrangement-warning{color:var(--el-color-warning);display:block}.arrangement-editor .el-alert{margin:8px 0}.arrangement-project-link{white-space:normal;height:auto;text-align:left}
.arrangement-edit-category>h2{font-size:17px;padding:10px 12px;margin:16px 0;background:var(--el-fill-color-light);border-left:3px solid var(--el-color-primary)}.arrangement-edit-platform>h3{font-size:15px;margin:14px 0 10px}.arrangement-edit-cell>h4{font-size:13px;color:var(--el-text-color-secondary);margin:10px 0 16px;overflow-wrap:anywhere}
.arrangement-target-dropdown.el-popper { max-width: calc(100vw - 32px); }
.arrangement-target-dropdown .el-select-dropdown__footer { padding: 0; border: 0; }
.arrangement-option-row { display: flex; align-items: center; gap: 12px; width: 100%; min-width: 0; }
.arrangement-option-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.arrangement-option-more { flex-shrink: 0; font-weight: normal; }
.arrangement-target-dropdown .el-select-dropdown__item.arrangement-project-option { height: auto; min-height: 64px; padding-top: 7px; padding-bottom: 7px; line-height: 24px; white-space: normal; }
.arrangement-project-languages { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 4px; font-weight: normal; line-height: 22px; }
.arrangement-project-languages .el-tag { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.arrangement-language-label { color: var(--el-text-color-secondary); font-size: 12px; }
.arrangement-child-order-badge { flex-shrink: 0; }
@media(max-width:600px){.arrangement-project-selector{grid-template-columns:1fr}}
</style>
