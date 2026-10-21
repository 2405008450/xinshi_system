<template>
  <el-config-provider :z-index="110000">
    <DraggableFormDialog :model-value="state.historyOpen" title="资料历史版本" width="min(760px, calc(100vw - 32px))" append-to-body @update:model-value="value => !value && closeHistory()">
      <p class="material-dialog-name">{{ state.historyRequest?.name }}</p>
      <el-alert v-if="historyError" :title="historyError" type="warning" :closable="false"><el-button link @click="loadHistory()">重试</el-button></el-alert>
      <div ref="historyPanel" v-loading="historyLoading" class="material-dialog-history">
        <div v-for="row in history" :key="row.id" class="material-dialog-row">
          <div><strong>V{{ row.version_no }} · {{ row.original_name }}</strong><p>{{ row.uploader_name }} · {{ formatBusinessDateTimeMinute(row.created_at) }}</p></div>
          <el-button link type="primary" @click="download(row)">下载</el-button>
        </div>
        <el-empty v-if="!historyLoading && !historyError && !history.length" description="暂无历史版本" :image-size="60" />
      </div>
      <template #footer><el-button @click="closeHistory">关闭</el-button></template>
    </DraggableFormDialog>
    <DraggableFormDialog :model-value="state.trashOpen" title="资料回收站" width="min(1080px, calc(100vw - 32px))" top="5vh" append-to-body class="material-trash-dialog" :before-close="done => !purging && !restoring && done()" @update:model-value="value => !value && !purging && !restoring && closeTrash()">
      <p class="material-dialog-hint">文件及全部历史版本长期保留，可恢复到原目录；只有超级管理员可以彻底删除。</p>
      <div class="material-dialog-tools">
        <el-input v-model="keyword" clearable placeholder="搜索文件名、原目录、删除人" aria-label="搜索回收站" @keyup.enter="searchTrash" />
        <el-button @click="searchTrash">查询</el-button>
        <BatchDeleteToolbar v-if="isSuperAdmin()" enter-label="彻底删除管理" mode-label="彻底删除模式" confirm-label="彻底删除所选" :active="purgeMode" :selected-count="selected.length" :loading="purging" @enter="enterPurge" @exit="exitPurge" @confirm="purgeSelected" />
      </div>
      <el-alert v-if="trashError" :title="trashError" type="error" :closable="false"><el-button link @click="loadTrash()">重试</el-button></el-alert>
      <el-table ref="trashTable" v-loading="trashLoading" :data="trashRows" row-key="file_id" border @selection-change="selected = $event">
        <el-table-column v-if="purgeMode" type="selection" width="48" />
        <el-table-column prop="original_name" label="文件名" min-width="160" show-overflow-tooltip />
        <el-table-column label="分类" width="90"><template #default="{ row }">{{ categories[row.category] }}</template></el-table-column>
        <el-table-column prop="original_folder_path" label="原目录" min-width="150" show-overflow-tooltip />
        <el-table-column prop="version_count" label="版本数" width="75" />
        <el-table-column prop="deleted_by_name" label="删除人" width="100" />
        <el-table-column label="删除时间" width="165"><template #default="{ row }">{{ formatBusinessDateTimeMinute(row.deleted_at) }}</template></el-table-column>
        <el-table-column v-if="!purgeMode" label="操作" width="85" fixed="right"><template #default="{ row }"><el-button link type="primary" :loading="restoring === row.file_id" :disabled="!!restoring" @click="restore(row)">恢复</el-button></template></el-table-column>
      </el-table>
      <template #footer>
        <el-pagination v-model:current-page="page" :page-size="20" :total="total" small layout="total, prev, pager, next" />
        <el-button :disabled="purging || !!restoring" @click="closeTrash">关闭</el-button>
      </template>
    </DraggableFormDialog>
  </el-config-provider>
</template>
<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useMaterialDialogs } from '@/composables/useMaterialDialogs'
import { useMaterialEditor } from '@/composables/useMaterialEditor'
import * as api from '@/api/annotationMaterials'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { isSuperAdmin } from '@/utils/permission'

const { state, closeHistory, closeTrash } = useMaterialDialogs()
const { state: editor, notifyMaterialSaved } = useMaterialEditor()
const categories = { project: '项目资料', quotation: '报价单', contract: '合同' }
const history = ref([]), historyError = ref(''), historyLoading = ref(false), historyPanel = ref()
const trashRows = ref([]), trashError = ref(''), trashLoading = ref(false), total = ref(0), page = ref(1), keyword = ref('')
const trashTable = ref(), selected = ref([]), purgeMode = ref(false), purging = ref(false), restoring = ref('')
let historyController, trashController, historySerial = 0, trashSerial = 0, timer, searchTimer
const errorText = error => error.detail || error.message || '操作失败，请重试'

async function loadHistory(silent = false) {
  if (!state.historyOpen || !state.historyRequest || (silent && historyController)) return
  historyController?.abort()
  const request = { ...state.historyRequest }, serial = ++historySerial, controller = new AbortController()
  historyController = controller
  if (!silent) historyLoading.value = true
  try {
    const rows = await api.listMaterialVersions(request.projectId, request.fileId, { signal: controller.signal })
    if (serial !== historySerial || controller.signal.aborted) return
    const scroll = historyPanel.value?.scrollTop || 0
    history.value = rows; historyError.value = ''
    await nextTick()
    if (historyPanel.value) historyPanel.value.scrollTop = scroll
  } catch (error) {
    if (serial === historySerial && !controller.signal.aborted) { historyError.value = errorText(error); history.value = [] }
  } finally { if (serial === historySerial) { historyLoading.value = false; historyController = null } }
}
async function download(row) {
  try { await api.downloadMaterial(state.historyRequest.projectId, row) } catch (error) { historyError.value = errorText(error) }
}
function exitPurge() { purgeMode.value = false; selected.value = []; trashTable.value?.clearSelection() }
function enterPurge() { exitPurge(); purgeMode.value = true }
async function loadTrash(silent = false) {
  if (!state.trashOpen || (silent && (trashController || purgeMode.value || purging.value || restoring.value))) return
  trashController?.abort()
  const serial = ++trashSerial, controller = new AbortController(), projectId = state.trashProjectId
  trashController = controller
  if (!silent) trashLoading.value = true
  try {
    const result = await api.listMaterialTrash(projectId, { keyword: keyword.value.trim(), page: page.value, limit: 20 }, { signal: controller.signal })
    if (serial !== trashSerial || controller.signal.aborted) return
    trashRows.value = result.items; total.value = result.total; trashError.value = ''
    const last = Math.max(1, Math.ceil(total.value / 20))
    if (page.value > last) page.value = last
  } catch (error) { if (serial === trashSerial && !controller.signal.aborted) trashError.value = errorText(error) }
  finally { if (serial === trashSerial) { trashController = null; trashLoading.value = false } }
}
function searchTrash() { clearTimeout(searchTimer); exitPurge(); if (page.value !== 1) page.value = 1; else void loadTrash() }
async function restore(row) {
  restoring.value = row.file_id
  try { await api.restoreMaterial(state.trashProjectId, row); notifyMaterialSaved(state.trashProjectId); await loadTrash(); ElMessage.success({ message: '文件及全部历史版本已恢复', customClass: 'material-action-message' }) }
  catch (error) { trashError.value = errorText(error) }
  finally { restoring.value = '' }
}
async function purgeSelected() {
  if (purging.value || !selected.value.length) return
  const rows = [...selected.value]
  const text = rows.length === 1 ? `彻底删除“${rows[0].original_name}”及其全部版本？此操作无法恢复。` : `彻底删除 ${rows.length} 个文件及全部版本，无法恢复。请输入“删除”继续。`
  try {
    if (rows.length === 1) await ElMessageBox.confirm(text, '彻底删除确认', { type: 'warning', modalClass: 'material-action-confirm' })
    else await ElMessageBox.prompt(text, '批量彻底删除', { type: 'warning', modalClass: 'material-action-confirm', inputValidator: value => value === '删除' || '请输入“删除”' })
  } catch { return }
  purging.value = true
  const failures = []
  let count = 0
  for (const row of rows) {
    try { await api.purgeMaterial(state.trashProjectId, row); count++ }
    catch (error) { failures.push({ row, reason: errorText(error) }) }
  }
  await loadTrash()
  if (count) notifyMaterialSaved(state.trashProjectId)
  selected.value = []; await nextTick(); trashTable.value?.clearSelection()
  if (failures.length) {
    for (const failure of failures) { const row = trashRows.value.find(item => item.file_id === failure.row.file_id); if (row) trashTable.value?.toggleRowSelection(row, true) }
    trashError.value = failures.map(item => `${item.row.original_name}：${item.reason}`).join('；')
  } else exitPurge()
  purging.value = false
  if (count) ElMessage.success({ message: `已彻底删除 ${count} 个文件`, customClass: 'material-action-message' })
}
watch(() => [state.historyOpen, state.historyRequest?.serial], () => {
  historyController?.abort(); ++historySerial; historyController = null
  history.value = []; historyError.value = ''; historyLoading.value = false
  if (state.historyOpen) void loadHistory()
})
watch(() => [state.trashOpen, state.trashProjectId], () => {
  trashController?.abort(); ++trashSerial; trashController = null
  exitPurge(); trashRows.value = []; trashError.value = ''; total.value = 0; keyword.value = ''; page.value = 1
  if (state.trashOpen) void loadTrash()
})
watch(keyword, value => { clearTimeout(searchTimer); if (!value.trim()) searchTrash(); else searchTimer = setTimeout(searchTrash, 400) })
watch(page, () => { exitPurge(); void loadTrash() })
function refreshVisible() { if (!document.hidden) { void loadHistory(true); void loadTrash(true) } }
watch(() => editor.savedTicks, refreshVisible, { deep: true })
onMounted(() => {
  // 初次按需挂载时，打开状态已经为 true。
  if (state.historyOpen) void loadHistory()
  if (state.trashOpen) void loadTrash()
  timer = setInterval(refreshVisible, 5000)
  window.addEventListener('focus', refreshVisible); document.addEventListener('visibilitychange', refreshVisible)
})
onBeforeUnmount(() => {
  clearInterval(timer); clearTimeout(searchTimer); historyController?.abort(); trashController?.abort()
  window.removeEventListener('focus', refreshVisible); document.removeEventListener('visibilitychange', refreshVisible)
  closeHistory(); closeTrash()
})
</script>
<style>
.material-dialog-name{margin:0 0 12px;overflow-wrap:anywhere}.material-dialog-hint{font-size:12px;color:var(--el-text-color-secondary)}
.material-dialog-history{max-height:min(520px,55vh);overflow-y:auto}.material-dialog-row{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--el-border-color-lighter)}.material-dialog-row p{margin:4px 0;font-size:12px;color:var(--el-text-color-secondary)}
.material-dialog-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}.material-dialog-tools>.el-input{max-width:300px}.material-trash-purge{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.material-trash-dialog>.el-dialog__footer{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.material-trash-dialog{height:85vh}.material-trash-dialog>.el-dialog__body>.el-table{min-height:180px}
.material-trash-dialog .batch-delete-toolbar{flex-wrap:wrap;white-space:normal}
</style>
