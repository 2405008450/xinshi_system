<template>
  <section class="wecom-groups" v-loading="loading">
    <div class="group-toolbar">
      <strong>{{ language }} · 企微项目大群</strong>
      <div class="group-toolbar-actions">
        <el-checkbox v-model="includeArchived" @change="loadData">显示归档群</el-checkbox>
        <el-button size="small" @click="loadData">刷新</el-button>
        <el-button v-if="writable" size="small" @click="openEditor('language')">编辑语种计划/备注</el-button>
        <el-button v-if="writable" size="small" type="primary" @click="openEditor('create')">新增企微群</el-button>
      </div>
    </div>
    <p class="language-memo"><strong>语种计划：</strong>{{ management?.plan || '-' }}　<strong>语种备注：</strong>{{ management?.remarks || '-' }}</p>
    <el-alert v-if="errorText" :title="errorText" type="error" :closable="false" />
    <el-table :data="groups" border size="small" class="wecom-groups-table">
      <el-table-column prop="name" label="企微项目大群群名" min-width="220" show-overflow-tooltip />
      <el-table-column label="是否已建" width="100"><template #default="{ row }"><el-tag :type="row.archived ? 'info' : row.isBuilt ? 'success' : 'warning'" size="small">{{ row.archived ? '已归档' : row.isBuilt ? '已建' : '未建' }}</el-tag></template></el-table-column>
      <el-table-column label="最新统计日期" width="150"><template #default="{ row }">{{ row.isBuilt ? formatOverviewDate(row.statisticsDate) : '-' }}</template></el-table-column>
      <el-table-column label="最新人数" width="110" align="right"><template #default="{ row }">{{ row.isBuilt ? formatOverviewCount(row.peopleCount) : '-' }}</template></el-table-column>
      <el-table-column label="较上次增减" width="110" align="right"><template #default="{ row }"><span :class="{ 'count-increase': row.change > 0, 'count-decrease': row.change < 0 }">{{ !row.isBuilt || row.change === null ? '-' : `${row.change > 0 ? '+' : ''}${formatOverviewCount(row.change)}` }}</span></template></el-table-column>
      <el-table-column label="详情" width="100" fixed="right"><template #default="{ row }">
        <TalentOverviewManagementDetail :group-id="row.id" :overview-key="overviewKey" :language="language" :writable="writable" :reload-token="reloadToken" @void="openVoid" />
      </template></el-table-column>
      <el-table-column v-if="writable" label="操作" width="230" fixed="right"><template #default="{ row }">
        <template v-if="!row.archived">
          <el-button link type="primary" @click="openEditor('edit', row)">编辑</el-button>
          <el-button link type="primary" :disabled="!row.isBuilt" @click="openEditor('count', row)">登记人数</el-button>
          <el-button link type="warning" :disabled="saving" @click="setArchive(row, true)">归档</el-button>
        </template>
        <el-button v-else link type="primary" :disabled="saving" @click="setArchive(row, false)">恢复</el-button>
      </template></el-table-column>
    </el-table>
    <p class="group-note">群人数未去重，各群统计日期可能不同；归档群不计入当前汇总。未登记显示“-”，明确的零显示“0”。</p>

    <DraggableFormDialog v-model="editorVisible" class="overview-wecom-editor" width="min(800px, calc(100vw - 32px))" top="5vh" append-to-body :close-on-click-modal="false" :before-close="beforeClose" @closed="clearFieldSearch">
      <template #header>
        <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="editorTitle" :fetch-suggestions="fetchFieldSuggestions" placeholder="搜索字段，如计划、人数" @select="locateDialogField" @clear="clearFieldSearch" />
      </template>
      <div ref="editorBodyRef">
        <el-alert v-if="conflict" title="资料已被其他人修改，当前草稿已保留。请复制需要保留的内容，再重新加载核对。" type="warning" :closable="false" show-icon>
          <el-button size="small" @click="reloadEditor">重新加载（替换草稿）</el-button>
        </el-alert>
        <AppForm ref="formRef" :model="form" :rules="rules" label-width="110px">
          <el-form-item label="所属语种"><ReadonlyField source="auto" :model-value="language" /></el-form-item>
          <template v-if="mode === 'create' || mode === 'edit'">
            <el-form-item label="群名" prop="name"><el-input v-model="form.name" maxlength="200" show-word-limit placeholder="未建群可填写拟用群名" /></el-form-item>
            <el-form-item label="是否已建" prop="isBuilt"><el-radio-group v-model="form.isBuilt" @change="value => { if (!value) form.builtDate = null }"><el-radio :value="true">已建</el-radio><el-radio :value="false">未建</el-radio></el-radio-group></el-form-item>
            <el-form-item v-if="form.isBuilt" label="建群日期" prop="builtDate"><el-date-picker v-model="form.builtDate" type="date" value-format="YYYY-MM-DD" placeholder="可选，未知时留空" /></el-form-item>
          </template>
          <template v-if="mode === 'language' || mode === 'create' || mode === 'edit'">
            <el-form-item label="计划" prop="plan"><el-input v-model="form.plan" type="textarea" :rows="5" maxlength="10000" show-word-limit placeholder="填写后续拓展或群运营计划" /></el-form-item>
            <el-form-item label="备注" prop="remarks"><el-input v-model="form.remarks" type="textarea" :rows="5" maxlength="10000" show-word-limit /></el-form-item>
          </template>
          <template v-if="mode === 'count'">
            <el-form-item label="群名"><ReadonlyField source="auto" :model-value="selectedGroup?.name" /></el-form-item>
            <el-form-item label="统计日期" prop="statisticsDate"><el-date-picker v-model="form.statisticsDate" type="date" value-format="YYYY-MM-DD" placeholder="支持补录历史日期" /></el-form-item>
            <el-form-item label="人数" prop="peopleCount"><el-input-number v-model="form.peopleCount" :min="0" :max="2147483647" :precision="0" :controls="false" placeholder="请输入人数，允许为0" /></el-form-item>
            <p class="group-note">同日最后一次登记生效；补录更早日期不覆盖较新日期的人数。系统自动记录操作人和操作时间。</p>
          </template>
          <template v-if="mode === 'void'">
            <el-form-item label="原统计日期"><ReadonlyField source="auto" :model-value="formatOverviewDate(selectedCount?.statisticsDate)" /></el-form-item>
            <el-form-item label="原人数"><ReadonlyField source="auto" :model-value="formatOverviewCount(selectedCount?.peopleCount)" /></el-form-item>
            <el-form-item label="作废原因" prop="reason"><el-input v-model="form.reason" type="textarea" :rows="4" maxlength="2000" show-word-limit /></el-form-item>
            <p class="group-note">原记录和作废信息均保留。作废后系统重新计算最新有效人数，正确数据请另行登记。</p>
          </template>
        </AppForm>
      </div>
      <template #footer><el-button :disabled="saving" @click="closeEditor">取消</el-button><el-button type="primary" :loading="saving" :disabled="conflict || !writable" @click="save">{{ mode === 'void' ? '确认作废' : '保存' }}</el-button></template>
    </DraggableFormDialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppForm from '@/components/common/AppForm.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import TalentOverviewManagementDetail from './TalentOverviewManagementDetail.vue'
import { getOverviewGroups, getOverviewLanguageManagement, getOverviewGroup, saveOverviewLanguageManagement, createOverviewGroup, updateOverviewGroup, registerOverviewGroupCount, voidOverviewGroupCount, archiveOverviewGroup } from '@/api/talents'
import { formatOverviewDate, formatOverviewCount, todayOverviewDate } from '@/utils/talentOverviewWecom'

const props = defineProps({ overviewKey: { type: String, required: true }, language: { type: String, required: true }, writable: Boolean })
const emit = defineEmits(['changed'])
const loading = ref(false)
const saving = ref(false)
const groups = ref([])
const management = ref(null)
const includeArchived = ref(false)
const errorText = ref('')
const reloadToken = ref(0)
const editorVisible = ref(false)
const mode = ref('create')
const selectedGroup = ref(null)
const selectedCount = ref(null)
const conflict = ref(false)
const formRef = ref(null)
const editorBodyRef = ref(null)
const baseline = ref('')
const form = reactive({ name: '', isBuilt: false, builtDate: null, plan: '', remarks: '', statisticsDate: '', peopleCount: undefined, reason: '' })
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(editorBodyRef)
const editorTitle = computed(() => ({ create: '新增企微大群', edit: '编辑企微大群', language: '编辑语种计划/备注', count: '登记群人数', void: '作废人数登记' })[mode.value])
const rules = computed(() => {
  if (mode.value === 'count') return { statisticsDate: [{ required: true, message: '请选择统计日期', trigger: 'change' }], peopleCount: [{ type: 'number', required: true, min: 0, message: '请输入非负整数人数', trigger: 'blur' }] }
  if (mode.value === 'void') return { reason: [{ required: true, whitespace: true, message: '请填写作废原因', trigger: 'blur' }] }
  if (mode.value === 'create' || mode.value === 'edit') return { name: [{ required: true, whitespace: true, message: '请输入群名', trigger: 'blur' }], isBuilt: [{ type: 'boolean', required: true, message: '请选择是否已建', trigger: 'change' }] }
  return {}
})
let loadSequence = 0
async function loadData() {
  const seq = ++loadSequence
  loading.value = true
  errorText.value = ''
  try {
    const [groupResult, memoResult] = await Promise.all([getOverviewGroups(props.overviewKey, includeArchived.value), getOverviewLanguageManagement(props.overviewKey)])
    if (seq !== loadSequence) return
    groups.value = groupResult
    management.value = memoResult
    reloadToken.value++
  } catch { if (seq === loadSequence) errorText.value = '群资料加载失败，请点击刷新重试' }
  finally { if (seq === loadSequence) loading.value = false }
}
async function openEditor(nextMode, row = null) {
  if (!props.writable || saving.value) return
  try {
    if (row) selectedGroup.value = await getOverviewGroup(row.id)
    if (nextMode === 'language') management.value = await getOverviewLanguageManagement(props.overviewKey)
    mode.value = nextMode
    conflict.value = false
    Object.assign(form, { name: '', isBuilt: false, builtDate: null, plan: '', remarks: '', statisticsDate: todayOverviewDate(), peopleCount: undefined, reason: '' })
    if (nextMode === 'edit') Object.assign(form, { name: selectedGroup.value.name, isBuilt: selectedGroup.value.isBuilt, builtDate: selectedGroup.value.builtDate, plan: selectedGroup.value.plan, remarks: selectedGroup.value.remarks })
    if (nextMode === 'language') Object.assign(form, { plan: management.value.plan, remarks: management.value.remarks })
    baseline.value = JSON.stringify(form)
    formRef.value?.clearValidate()
    clearFieldSearch()
    editorVisible.value = true
  } catch { ElMessage.error('最新资料加载失败，请重试') }
}
async function openVoid({ group, record }) {
  selectedCount.value = record
  await openEditor('void', group)
}
async function discard() {
  if (!editorVisible.value || baseline.value === JSON.stringify(form)) return true
  try { await ElMessageBox.confirm('当前表单有未保存内容，确定放弃吗？', '未保存修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' }); return true }
  catch { return false }
}
async function beforeClose(done) { if (!saving.value && await discard()) done() }
async function closeEditor() { if (!saving.value && await discard()) editorVisible.value = false }
async function reloadEditor() {
  if (!await discard()) return
  await openEditor(mode.value, mode.value === 'language' || mode.value === 'create' ? null : selectedGroup.value)
}
function showError(error) {
  if (error?.response?.status === 409) { conflict.value = true; ElMessage.warning('资料已更新，草稿已保留，请重新加载核对'); return }
  const detail = error?.detail || error?.response?.data?.detail
  ElMessage.error(typeof detail === 'string' ? detail : '保存失败，请重试')
}
async function save() {
  if (!props.writable || saving.value || conflict.value) return
  if (!await formRef.value?.validate().catch(() => false)) return
  if (saving.value) return
  saving.value = true
  try {
    const memo = { plan: form.plan, remarks: form.remarks }
    if (mode.value === 'language') await saveOverviewLanguageManagement(props.overviewKey, { ...memo, expectedRevision: management.value.revision })
    else if (mode.value === 'create' || mode.value === 'edit') {
      const payload = { ...memo, name: form.name.trim(), isBuilt: form.isBuilt, builtDate: form.isBuilt ? form.builtDate || null : null }
      if (mode.value === 'create') await createOverviewGroup(props.overviewKey, payload)
      else await updateOverviewGroup(selectedGroup.value.id, { ...payload, expectedRevision: selectedGroup.value.revision })
    } else if (mode.value === 'count') await registerOverviewGroupCount(selectedGroup.value.id, { expectedRevision: selectedGroup.value.revision, statisticsDate: form.statisticsDate, peopleCount: form.peopleCount })
    else await voidOverviewGroupCount(selectedGroup.value.id, selectedCount.value.id, { expectedRevision: selectedGroup.value.revision, reason: form.reason.trim() })
    editorVisible.value = false
    await loadData()
    emit('changed')
    ElMessage.success('已保存')
  } catch (error) { showError(error) }
  finally { saving.value = false }
}
async function setArchive(row, archived) {
  if (!props.writable || saving.value) return
  try {
    await ElMessageBox.confirm(archived ? `归档“${row.name}”后将退出当前汇总，资料与历史仍保留。` : `恢复“${row.name}”并重新参与当前汇总？`, archived ? '归档群' : '恢复群', { type: 'warning' })
  } catch { return }
  saving.value = true
  try {
    await archiveOverviewGroup(row.id, { expectedRevision: row.revision, archived })
    await loadData()
    emit('changed')
    ElMessage.success(archived ? '群已归档' : '群已恢复')
  } catch (error) {
    if (error?.response?.status === 409) { ElMessage.warning('群已被其他人更新，请刷新后核对'); await loadData() }
    else showError(error)
  } finally { saving.value = false }
}
onBeforeRouteLeave(async () => !saving.value && await discard())
onMounted(loadData)
</script>

<style scoped>
.wecom-groups { padding: 16px 22px; background: var(--el-fill-color-extra-light); }
.group-toolbar, .group-toolbar-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.group-toolbar { justify-content: space-between; }
.language-memo { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 90px; overflow-y: auto; line-height: 1.7; color: var(--el-text-color-regular); }
.group-note { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.7; }
.count-increase { color: var(--el-color-success); }
.count-decrease { color: var(--el-color-danger); }
</style>
<style>
.el-dialog.overview-wecom-editor { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.overview-wecom-editor .el-dialog__header, .overview-wecom-editor .el-dialog__footer { flex-shrink: 0; }
.overview-wecom-editor .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.overview-wecom-editor .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-extra-light); padding-top: 14px; }
</style>
