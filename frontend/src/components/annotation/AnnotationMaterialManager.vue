<template>
  <div class="material-manager" v-loading="loading">
    <el-alert v-if="deleteError" :title="deleteError" type="error" :closable="false" class="material-alert" />
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" class="material-alert">
      <el-button link type="primary" @click="reload">重新加载</el-button>
    </el-alert>

    <section class="material-section material-section--primary" data-dialog-field-search-label="项目资料">
      <div class="material-section-header">
        <div class="material-section-title">
          <strong>项目资料</strong>
          <span class="material-section-hint">{{ !readonly ? '单文件 ≤ 100MB，保存项目后生效' : canManageSaved ? '单文件 ≤ 100MB，支持多选与拖拽直接上传' : '' }}</span>
        </div>
        <div v-if="canManageSaved" class="material-manager-tools">
          <el-button class="material-tool-btn" size="small" :disabled="deleting" @click="openTrash(projectId)">回收站</el-button>
          <BatchDeleteToolbar :active="deleteMode" :selected-count="selectedIds.length" :loading="deleting" @enter="enterDelete" @exit="exitDelete" @confirm="deleteSelected" />
        </div>
      </div>
      <AnnotationMaterialExplorer
        :key="`${projectId}:${active}`" v-model:folder-id="selectedFolderId"
        :folders="allFolders" :files="categoryRows('project')" :pending="categoryPending('project')"
        :readonly="readonly" :can-upload="canMutate" :disabled="disabled || deleting || loading || !!loadError" :format-size="sizeText" :format-time="timeText"
        :online-edit="canOnlineEdit && !deleteMode" :edit-blocked="editBlocked" :create-blocked="createBlocked"
        :delete-mode="deleteMode" :checked-ids="selectedIds" @toggle-delete="toggleDelete"
        @edit="editOnline" @edit-window="row => editOnline(row, true)" @create-document="openDocumentCreator"
        @create="openFolderCreator" @upload="files => addFiles(files, 'project')"
        @replace="({ files, fileId }) => addFiles(files, 'project', fileId)"
        @download="download" @history="showHistory" @remove="remove" @retry="send" @discard="discard"
      />
    </section>

    <div class="material-secondary-grid">
      <section v-for="category in secondaryCategories" :key="category.key" class="material-card" :data-dialog-field-search-label="category.label">
        <div class="material-card-header">
          <div class="material-card-title">
            <strong>{{ category.label }}</strong>
            <span class="material-card-count">{{ categoryRows(category.key).length }}</span>
          </div>
          <label v-if="canMutate && !deleteMode" class="material-upload-btn" :class="{ disabled: disabled || loading || !!loadError }">
            <el-icon><Upload /></el-icon>
            <span>上传文件</span>
            <input type="file" multiple :disabled="disabled || loading || !!loadError" :aria-label="`上传${category.label}`" @change="selectFiles($event, category.key)">
          </label>
        </div>
        <div class="material-card-body">
          <div v-for="row in categoryRows(category.key)" :key="row.file_id" class="material-row">
            <el-checkbox v-if="deleteMode" :model-value="selectedIds.includes(row.file_id)" :disabled="deleting" :aria-label="`选择删除${row.original_name}`" @change="toggleDelete(row)" />
            <div class="material-info"><span :title="row.original_name">{{ row.original_name }}</span><small>{{ sizeText(row.file_size) }} · V{{ row.version_no }} · {{ row.uploader_name }} · {{ timeText(row.created_at) }}</small></div>
            <div class="material-actions">
              <el-button link type="primary" size="small" @click="download(row)">下载</el-button>
              <el-button link type="primary" size="small" @click="showHistory(row)">历史</el-button>
              <label v-if="canMutate && !deleteMode && !hasReplacement(row.file_id)" class="material-upload-link" :class="{ disabled }">上传新版<input type="file" :disabled="disabled" :aria-label="`为${row.original_name}上传新版`" @change="selectFiles($event, category.key, row.file_id)"></label>
              <el-button v-if="!readonly" link type="danger" size="small" :disabled="disabled" @click="remove(row)">移除</el-button>
            </div>
          </div>
          <div v-for="item in categoryPending(category.key)" :key="item.key" class="material-row">
            <div class="material-info"><span>{{ item.file.name }} <el-tag size="small">{{ item.status === 'uploading' ? '上传中' : item.fileId ? '待保存新版' : '待保存新文件' }}</el-tag></span>
              <el-progress v-if="item.status === 'uploading'" :percentage="item.progress" :stroke-width="4" />
              <small v-else-if="item.status === 'queued'">等待上传</small>
              <small v-else :class="{ 'material-error': item.status === 'failed' }">{{ item.error || '已暂存，等待保存项目' }}</small>
            </div>
            <el-button v-if="item.status === 'failed'" link type="primary" size="small" :disabled="disabled" @click="send(item)">重试</el-button>
            <el-button link size="small" :disabled="disabled" @click="discard(item)">取消</el-button>
          </div>
          <div v-if="!categoryRows(category.key).length && !categoryPending(category.key).length" class="material-card-empty">暂无{{ category.label }}文件</div>
        </div>
      </section>
    </div>

    <div v-if="removed.length" class="material-hint material-removed-bar">{{ removed.length }} 个文件将在保存后移入回收站（含全部版本）。<el-button link :disabled="disabled" @click="removed = []">撤销移除</el-button></div>
    <DraggableFormDialog v-model="folderCreatorVisible" :title="folderLevel === 1 ? '新建一级文件夹' : '新建二级文件夹'" width="min(480px, calc(100vw - 32px))" append-to-body class="material-folder-dialog">
      <AppForm ref="folderFormRef" :model="folderForm" :rules="folderRules" label-width="90px" @submit.prevent="confirmFolder">
        <el-form-item v-if="folderLevel === 2" label="一级文件夹" prop="parentId"><el-select v-model="folderForm.parentId" style="width:100%" placeholder="请选择一级文件夹"><el-option v-for="folder in rootFolders" :key="folder.id" :label="folder.name" :value="folder.id" /></el-select></el-form-item>
        <el-form-item label="文件夹名称" prop="name"><el-input v-model="folderForm.name" maxlength="100" show-word-limit placeholder="请输入文件夹名称" @keyup.enter="confirmFolder" /></el-form-item>
        <p class="material-hint">{{ canManageSaved ? '创建后将立即保存到当前项目资料中。' : '创建后随项目保存生效，取消编辑不会保存文件夹。' }}</p>
      </AppForm>
      <template #footer><el-button @click="folderCreatorVisible = false">取消</el-button><el-button type="primary" :loading="folderSaving" :disabled="disabled" @click="confirmFolder">创建</el-button></template>
    </DraggableFormDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import AnnotationMaterialExplorer from '@/components/annotation/AnnotationMaterialExplorer.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import * as api from '@/api/annotationMaterials'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { folderNameError, folderParentId, folderPath, newFolderId, withDefaultProjectFolder } from '@/utils/annotationMaterialFolders'
import { onlineEditBlocker } from '@/utils/materialDocument'
import { useMaterialEditor } from '@/composables/useMaterialEditor'
import { useMaterialDialogs } from '@/composables/useMaterialDialogs'
import { hasPermission } from '@/utils/permission'
import { openOfficePage } from '@/utils/officePage'

const props = defineProps({ projectId: { type: String, default: '' }, readonly: Boolean, active: { type: Boolean, default: true }, disabled: Boolean })
const emit = defineEmits(['busy'])
const { openHistory, openTrash } = useMaterialDialogs()
const canManageSaved = computed(() => props.readonly && !!props.projectId && hasPermission('projects:write'))
const canMutate = computed(() => !props.readonly || canManageSaved.value)
const deleteMode = ref(false), deleting = ref(false), folderSaving = ref(false), selectedIds = ref([]), deleteError = ref('')
function syncBusy() {
  emit('busy', deleting.value || folderSaving.value || pending.value.some(row => row.status === 'uploading' || row.status === 'queued'))
}
function exitDelete() { if (!deleting.value) { deleteMode.value = false; selectedIds.value = []; deleteError.value = '' } }
function enterDelete() { if (!props.disabled && !loading.value && !loadError.value) { exitDelete(); deleteMode.value = true } }
function toggleDelete(row) { if (!deleting.value) selectedIds.value = selectedIds.value.includes(row.file_id) ? selectedIds.value.filter(id => id !== row.file_id) : [...selectedIds.value, row.file_id] }
async function deleteSelected() {
  if (deleting.value || !selectedIds.value.length || !canManageSaved.value) return
  const targets = rows.value.filter(row => selectedIds.value.includes(row.file_id)), project = props.projectId
  if (!targets.length) { exitDelete(); return }
  emit('busy', true); deleting.value = true
  try {
    const message = targets.length === 1 ? `将“${targets[0].original_name}”及全部历史版本移入回收站？` : `将所选 ${targets.length} 个文件及全部历史版本移入回收站？请输入“删除”继续。`
    try {
      if (targets.length === 1) await ElMessageBox.confirm(message, '删除文件', { type: 'warning', modalClass: 'material-action-confirm' })
      else await ElMessageBox.prompt(message, '批量删除文件', { type: 'warning', modalClass: 'material-action-confirm', inputValidator: value => value === '删除' || '请输入“删除”' })
    } catch { return }
    const failures = []; let count = 0
    for (const row of targets) {
      try { await api.trashMaterial(project, row.file_id); count++ }
      catch (error) { failures.push({ id: row.file_id, text: `${row.original_name}：${error.detail || error.message || '删除失败'}` }) }
    }
    if (count) { notifyMaterialSaved(project); await reload(); ElMessage.success({ message: `已将 ${count} 个文件移入回收站`, customClass: 'material-action-message' }) }
    selectedIds.value = failures.map(item => item.id)
    deleteError.value = failures.map(item => item.text).join('；')
    if (!failures.length) deleteMode.value = false
  } finally { deleting.value = false; emit('busy', false) }
}
const categories = [{ key: 'project', label: '项目资料' }, { key: 'quotation', label: '报价单' }, { key: 'contract', label: '合同' }]
const secondaryCategories = categories.filter(item => item.key !== 'project')
const rows = ref([]), pending = ref([]), removed = ref([]), loading = ref(false), loadError = ref('')
const savedFolders = ref([]), createdFolders = ref([]), selectedFolderId = ref(null)
const defaultFolderId = ref(newFolderId())
const allFolders = computed(() => withDefaultProjectFolder([
  ...savedFolders.value, ...createdFolders.value.map(folder => ({ ...folder, pending: true })),
], defaultFolderId.value))
const rootFolders = computed(() => allFolders.value.filter(folder => !folder.parent_id))
const folderCreatorVisible = ref(false), folderLevel = ref(1), folderFormRef = ref(null)
const folderForm = reactive({ name: '', parentId: null })
const folderRules = {
  parentId: [{ required: true, message: '请选择一级文件夹', trigger: 'change' }],
  name: [{ validator: (_rule, value, callback) => {
    const error = folderNameError(value, allFolders.value, folderLevel.value === 2 ? folderForm.parentId : null)
    callback(error ? new Error(error) : undefined)
  }, trigger: 'blur' }],
}

// 在线编辑即时生成新版本，不依赖项目表单保存；只读浮层中有写权限也可使用。
const { state: editorState, openMaterialEditor, notifyMaterialSaved } = useMaterialEditor()
const canOnlineEdit = computed(() => Boolean(props.projectId) && (hasPermission('projects:read') || hasPermission('projects:write')))
const editBlocked = row => {
  if (props.disabled || loading.value || loadError.value) return '资料加载或项目保存中，请稍候'
  if (hasReplacement(row.file_id)) return '该文件有待保存的新版，请先保存项目或取消上传'
  if (!/\.(docx|xlsx)$/i.test(row.original_name) && !hasPermission('projects:write')) return '没有在线编辑权限，请使用下载功能'
  return onlineEditBlocker(row)
}
const currentFolder = computed(() => allFolders.value.find(folder => folder.id === selectedFolderId.value))
const currentFolderName = computed(() => folderPath(allFolders.value, selectedFolderId.value))
const createBlocked = computed(() => {
  if (!hasPermission('projects:write')) return '没有新建文档权限'
  if (props.disabled || loading.value || loadError.value) return '资料加载或项目保存中，请稍候'
  return currentFolder.value?.pending || currentFolder.value?.default ? '当前文件夹尚未保存，请先保存项目后再新建文档' : ''
})
function editOnline(row, smallWindow = false) {
  const reason = editBlocked(row)
  if (reason) { ElMessage.warning(reason); return }
  openEditor({ projectId: props.projectId, file: row }, smallWindow)
}
function openEditor(request, smallWindow = false) {
  const office = ['docx', 'xlsx'].includes(request.create?.kind) || /\.(docx|xlsx)$/i.test(request.file?.original_name || '')
  if (office && !smallWindow) {
    if (!openOfficePage(request)) ElMessage.warning('浏览器阻止了新标签页，请允许此站点打开弹出窗口后重试，或在文件菜单选择“小窗编辑”')
  } else if (!openMaterialEditor(request)) ElMessage.warning('已有正在在线编辑的文件，请先保存或关闭')
}
function openDocumentCreator(kind) {
  if (createBlocked.value) { ElMessage.warning(createBlocked.value); return }
  // 文件名在全局编辑器内填写：资料浮层关闭后命名和编辑内容仍然保留。
  const siblingNames = [
    ...rows.value.filter(row => row.category === 'project' && (row.folder_id || null) === selectedFolderId.value).map(row => row.original_name),
    ...pending.value.filter(item => item.category === 'project' && !item.fileId && item.folder_id === selectedFolderId.value).map(item => item.file.name),
  ]
  const create = { kind, folderId: selectedFolderId.value, folderName: currentFolderName.value, siblingNames }
  openEditor({ projectId: props.projectId, create })
}
let generation = 0, requestId = 0, nextKey = 0
let reloadController = null, refreshTimer = null
const sizeText = size => size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(size / 1024)} KB`
// 后端资料时间使用 UTC，显式标记时区后交给公共格式化函数。
const timeText = value => formatBusinessDateTimeMinute(value && !/(Z|[+-]\d{2}:\d{2})$/.test(value) ? `${value}Z` : value)
const inCurrentFolder = row => row.category !== 'project' || (row.folder_id || null) === selectedFolderId.value
const categoryRows = category => rows.value.filter(row => row.category === category && inCurrentFolder(row) && !removed.value.includes(row.file_id))
const categoryPending = category => pending.value.filter(item => item.category === category && inCurrentFolder(item))
const hasReplacement = id => pending.value.some(item => item.fileId === id)

async function ensurePersistedFolder(folderId) {
  if (!folderId) return null
  const folder = allFolders.value.find(item => item.id === folderId)
  if (!folder?.default) return folderId
  const created = await api.createMaterialFolder(props.projectId, { id: folder.id, parent_id: null, name: folder.name })
  if (!savedFolders.value.some(item => item.id === created.id)) savedFolders.value = [...savedFolders.value, created]
  if (selectedFolderId.value === folderId) selectedFolderId.value = created.id
  return created.id
}

async function openFolderCreator(level) {
  if (props.disabled || !canMutate.value || deleteMode.value || loading.value || loadError.value) return
  folderLevel.value = level
  folderForm.name = ''; folderForm.parentId = folderParentId(allFolders.value, selectedFolderId.value)
  folderCreatorVisible.value = true
  await nextTick(); folderFormRef.value?.clearValidate()
}
let creatingFolder = false
async function confirmFolder() {
  if (creatingFolder || props.disabled || !canMutate.value || !folderCreatorVisible.value) return
  creatingFolder = true
  const session = generation
  try {
    const valid = await folderFormRef.value?.validate().catch(() => false)
    if (!valid || session !== generation || !folderCreatorVisible.value) return
    if (canManageSaved.value) {
      folderSaving.value = true; syncBusy()
      try {
        const parentId = folderLevel.value === 2 ? await ensurePersistedFolder(folderForm.parentId) : null
        const created = await api.createMaterialFolder(props.projectId, { id: newFolderId(), parent_id: parentId, name: folderForm.name.trim() })
        if (session !== generation) return
        if (!savedFolders.value.some(item => item.id === created.id)) savedFolders.value = [...savedFolders.value, created]
        selectedFolderId.value = created.id
        folderCreatorVisible.value = false
        notifyMaterialSaved(props.projectId)
        ElMessage.success({ message: `已创建文件夹“${created.name}”`, customClass: 'material-action-message' })
      } catch (error) {
        ElMessage.error({ message: error.detail || error.message || '创建文件夹失败', customClass: 'material-action-message' })
      } finally {
        folderSaving.value = false; syncBusy()
      }
      return
    }
    if (allFolders.value.filter(folder => folder.pending || folder.default).length >= 200) { ElMessage.warning('每次保存最多创建200个文件夹'); return }
    const id = newFolderId()
    createdFolders.value.push({ id, parent_id: folderLevel.value === 2 ? folderForm.parentId : null, name: folderForm.name.trim() })
    selectedFolderId.value = id; folderCreatorVisible.value = false
  } finally { creatingFolder = false }
}

async function reload(options = {}) {
  const silent = options.silent === true
  if (silent && (reloadController || !props.active || document.hidden || props.disabled)) return
  reloadController?.abort()
  const serial = ++requestId
  if (!props.projectId) { rows.value = []; savedFolders.value = []; loading.value = false; loadError.value = ''; return }
  const controller = new AbortController()
  reloadController = controller
  if (!silent) { loading.value = true; loadError.value = '' }
  try {
    const config = { signal: controller.signal }
    const [result, directories] = await Promise.all([api.listMaterials(props.projectId, config), api.listMaterialFolders(props.projectId, config)])
    if (serial === requestId) {
      rows.value = result; savedFolders.value = directories; loadError.value = ''
      // 只更新云端已保存资料，保留当前表单的待上传文件、移除标记和新建目录。
    }
  }
  catch (error) { if (serial === requestId && !controller.signal.aborted && !silent) loadError.value = error.detail || '项目资料加载失败' }
  finally { if (serial === requestId) { loading.value = false; reloadController = null } }
}
function refreshVisible() { if (props.active && props.projectId && !document.hidden) void reload({ silent: true }) }

function release(id) {
  if (id) void api.cancelMaterialUpload(id).catch(() => { /* 断网时由云端24小时过期清理兜底。 */ })
}
function reset() {
  generation += 1; requestId += 1
  reloadController?.abort(); reloadController = null
  pending.value.forEach(item => { item.controller?.abort(); release(item.upload?.id) })
  pending.value = []; removed.value = []; rows.value = []; loadError.value = ''; loading.value = false
  exitDelete()
  savedFolders.value = []; createdFolders.value = []; selectedFolderId.value = null; folderCreatorVisible.value = false
  defaultFolderId.value = newFolderId()
}
async function send(item) {
  if (pending.value.filter(row => row !== item && row.status === 'uploading').length >= 3) { item.status = 'queued'; syncBusy(); return }
  const session = generation
  item.status = 'uploading'; item.error = ''; item.progress = item.upload ? 95 : 0; item.controller = new AbortController()
  syncBusy()
  try {
    const result = item.upload || await api.uploadMaterial(item.file, event => { item.progress = Math.min(95, Math.round(event.loaded / (event.total || item.file.size) * 95)) }, item.controller.signal)
    if (session !== generation || !pending.value.includes(item)) { if (!item.upload) release(result.id); return }
    item.upload = result
    if (canManageSaved.value) {
      const folderId = item.category === 'project' && !item.fileId ? await ensurePersistedFolder(item.folder_id) : null
      await api.commitMaterial(props.projectId, { upload_id: result.id, category: item.category, file_id: item.fileId || null, folder_id: folderId })
      if (session !== generation) return
      pending.value = pending.value.filter(row => row !== item)
      notifyMaterialSaved(props.projectId)
      await reload({ silent: true })
      ElMessage.success({ message: `已上传“${item.file.name}”`, customClass: 'material-action-message' })
      return
    }
    item.status = 'ready'; item.progress = 100
  } catch (error) {
    if (session !== generation || !pending.value.includes(item)) return
    item.status = 'failed'; item.error = error.detail || error.message || '上传失败，请重试或取消此文件'
  } finally {
    if (session === generation) {
      const next = pending.value.find(row => row.status === 'queued')
      if (next) void send(next)
      syncBusy()
    }
  }
}
function selectFiles(event, category, fileId = null) {
  const files = Array.from(event.target.files || []); event.target.value = ''
  addFiles(files, category, fileId)
}
function addFiles(files, category, fileId = null) {
  if (props.disabled || !canMutate.value || deleteMode.value || loading.value || loadError.value) return
  for (const file of files) {
    if (!file.size || file.size > 100 * 1024 * 1024) { ElMessage.error(`${file.name}：文件不能为空或超过100MB`); continue }
    if (pending.value.length >= 200) { ElMessage.warning('每次保存最多处理200个文件'); break }
    if (fileId && hasReplacement(fileId)) break
    const folderId = category === 'project' ? (fileId ? rows.value.find(row => row.file_id === fileId)?.folder_id || null : selectedFolderId.value) : null
    const item = { key: ++nextKey, file, fileId, category, folder_id: folderId, status: 'queued', progress: 0 }
    pending.value.push(item)
    void send(pending.value[pending.value.length - 1])
  }
}
function discard(item) { item.controller?.abort(); release(item.upload?.id); pending.value = pending.value.filter(row => row !== item); syncBusy() }
async function remove(row) {
  try { await ElMessageBox.confirm(`保存项目后将“${row.original_name}”及其全部历史版本移入回收站，可恢复。是否标记移除？`, '移除项目资料', { type: 'warning' }) } catch { return }
  pending.value.filter(item => item.fileId === row.file_id).forEach(discard)
  removed.value.push(row.file_id)
}
async function download(row) { try { await api.downloadMaterial(props.projectId, row) } catch (error) { ElMessage.error(error.detail || '资料下载失败') } }
function showHistory(row) { openHistory(props.projectId, row) }
function validate() {
  if (loading.value || loadError.value) { ElMessage.warning('请等待资料加载完成或重新加载后保存'); return false }
  const unfinished = pending.value.find(item => item.status !== 'ready')
  if (unfinished) { if (unfinished.category === 'project') selectedFolderId.value = unfinished.folder_id; ElMessage.warning('请等待上传完成，并重试或取消失败的文件'); return false }
  if (pending.value.some(item => new Date(`${item.upload.expires_at}Z`).getTime() <= Date.now())) { ElMessage.warning('暂存文件已过期，请取消后重新上传'); return false }
  return true
}
function changes() {
  return { additions: pending.value.map(item => ({ uploadId: item.upload.id, category: item.category, fileId: item.fileId, folderId: item.folder_id })), removedFileIds: [...removed.value], createdFolders: allFolders.value.filter(folder => folder.pending || folder.default).map(folder => ({ id: folder.id, parentId: folder.parent_id, name: folder.name })) }
}
function saved() { pending.value = []; removed.value = []; createdFolders.value = []; void reload() }
watch(() => [props.projectId, props.active], () => { reset(); if (props.active) void reload() }, { immediate: true })
// 在线编辑保存后刷新同一项目的全部资料组件，保留表单中未保存的暂存与目录。
watch(() => editorState.savedTicks[props.projectId], (value, old) => { if (value && value !== old && props.active) void reload() })
watch(selectedFolderId, exitDelete)
onMounted(() => {
  refreshTimer = window.setInterval(refreshVisible, 5000)
  window.addEventListener('focus', refreshVisible)
  document.addEventListener('visibilitychange', refreshVisible)
})
onBeforeUnmount(() => {
  window.clearInterval(refreshTimer)
  window.removeEventListener('focus', refreshVisible)
  document.removeEventListener('visibilitychange', refreshVisible)
  reset()
})
defineExpose({ validate, changes, saved, reload })
</script>

<style scoped>
.material-manager { display: flex; flex-direction: column; gap: 14px; width: 100%; min-width: 0; }
.material-alert { margin-bottom: 0; }
.material-section { display: flex; flex-direction: column; gap: 8px; }
.material-section-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.material-section-title { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; min-width: 0; }
.material-section-title strong { font-size: 14px; font-weight: 600; color: var(--color-text-primary, #111827); }
.material-section-hint { font-size: 12px; color: var(--color-text-muted, #64748b); }
.material-manager-tools { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.material-manager-tools :deep(.el-button) { height: 30px; min-height: 30px; padding: 0 10px; border-radius: 6px; font-size: 12.5px; margin: 0; }
.material-manager-tools :deep(.batch-delete-toolbar) { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; white-space: normal; }
.material-secondary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.material-card { display: flex; flex-direction: column; border: 1px solid var(--color-border, #e2e8f0); border-radius: 8px; background: #fff; overflow: hidden; min-width: 0; }
.material-card-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 12px; background: #f8fafc; border-bottom: 1px solid #eef2f6; }
.material-card-title { display: flex; align-items: center; gap: 6px; min-width: 0; }
.material-card-title strong { font-size: 13px; font-weight: 600; color: #1e293b; }
.material-card-count { display: inline-flex; align-items: center; justify-content: center; min-width: 20px; height: 18px; padding: 0 6px; border-radius: 9px; background: #e8eef5; color: #475569; font-size: 11px; font-variant-numeric: tabular-nums; }
.material-card-body { padding: 8px 12px; min-height: 64px; display: flex; flex-direction: column; justify-content: center; }
.material-card-empty { text-align: center; color: #94a3b8; font-size: 12px; padding: 10px 0; }
.material-upload-btn { display: inline-flex; align-items: center; justify-content: center; gap: 4px; box-sizing: border-box; height: 26px; padding: 0 9px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; color: #334155; font-size: 12px; font-weight: 500; cursor: pointer; position: relative; transition: background-color .14s ease, border-color .14s ease, color .14s ease; }
.material-upload-btn:hover:not(.disabled) { background: #eef3f8; border-color: #94a3b8; color: #1e293b; }
.material-upload-btn input,.material-upload-link input { position: absolute; inset: 0; width: 100%; opacity: 0; cursor: pointer; }
.material-upload-btn.disabled,.material-upload-link.disabled { opacity: .5; cursor: not-allowed; }
.material-upload-btn:focus-within,.material-upload-link:focus-within { outline: 2px solid var(--color-primary, #334155); outline-offset: 2px; }
.material-upload-link { position: relative; display: inline-flex; align-items: center; color: var(--color-primary, #334155); font-size: 12px; cursor: pointer; padding: 2px 4px; border-radius: 4px; }
.material-upload-link:hover:not(.disabled) { background: #f1f5f9; }
.material-row,.material-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.material-row { padding: 7px 0; border-bottom: 1px solid #f1f5f9; }
.material-row:last-child { border-bottom: 0; }
.material-info { flex: 1; min-width: 120px; overflow-wrap: anywhere; font-size: 12.5px; color: #1e293b; }
.material-info small { display: block; color: var(--color-text-muted, #64748b); font-size: 11px; margin-top: 2px; }
.material-hint { color: var(--color-text-muted, #64748b); font-size: 12px; line-height: 1.6; }
.material-removed-bar { padding: 8px 12px; border-radius: 6px; background: #fef9ec; border: 1px solid #fde68a; color: #92400e; }
.material-info .material-error { color: var(--el-color-danger); }
.material-history { max-height: 55vh; overflow-y: auto; }
@media (max-width: 640px) {
  .material-secondary-grid { grid-template-columns: minmax(0, 1fr); }
  .material-actions { width: 100%; }
}
</style>

<style>
.el-dialog.material-folder-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.material-folder-dialog .el-dialog__header,.material-folder-dialog .el-dialog__footer { flex-shrink: 0; }
.material-folder-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.material-folder-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); }
</style>
