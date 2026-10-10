<template>
  <div class="material-manager" v-loading="loading">
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false">
      <el-button link type="primary" @click="reload">重新加载</el-button>
    </el-alert>
    <p v-if="!readonly" class="material-hint">单文件最大 100MB，可一次选择多个文件。文件变更在保存项目后生效，取消编辑不会改变已保存资料。</p>
    <section v-for="category in categories" :key="category.key" class="material-category" :data-dialog-field-search-label="category.label">
      <div class="material-heading">
        <strong>{{ category.label }}</strong>
        <label v-if="!readonly && category.key !== 'project'" class="material-upload" :class="{ disabled }">
          上传文件<input type="file" multiple :disabled="disabled || loading || !!loadError" :aria-label="`上传${category.label}`" @change="selectFiles($event, category.key)">
        </label>
      </div>
      <AnnotationMaterialExplorer
        v-if="category.key === 'project'" :key="`${projectId}:${active}`" v-model:folder-id="selectedFolderId"
        :folders="allFolders" :files="categoryRows('project')" :pending="categoryPending('project')"
        :readonly="readonly" :disabled="disabled || loading || !!loadError" :format-size="sizeText" :format-time="timeText"
        @create="openFolderCreator" @upload="files => addFiles(files, 'project')"
        @replace="({ files, fileId }) => addFiles(files, 'project', fileId)"
        @download="download" @history="showHistory" @remove="remove" @retry="send" @discard="discard"
      />
      <div v-else>
          <div v-for="row in categoryRows(category.key)" :key="row.file_id" class="material-row">
            <div class="material-info"><span>{{ row.original_name }}</span><small>{{ sizeText(row.file_size) }} · V{{ row.version_no }} · {{ row.uploader_name }} · {{ timeText(row.created_at) }}</small></div>
            <div class="material-actions">
              <el-button link type="primary" @click="download(row)">下载</el-button>
              <el-button link type="primary" @click="showHistory(row)">历史版本</el-button>
              <label v-if="!readonly && !hasReplacement(row.file_id)" class="material-upload" :class="{ disabled }">上传新版<input type="file" :disabled="disabled" :aria-label="`为${row.original_name}上传新版`" @change="selectFiles($event, category.key, row.file_id)"></label>
              <el-button v-if="!readonly" link type="danger" :disabled="disabled" @click="remove(row)">移除</el-button>
            </div>
          </div>
          <div v-for="item in categoryPending(category.key)" :key="item.key" class="material-row">
            <div class="material-info"><span>{{ item.file.name }} <el-tag size="small">{{ item.fileId ? '待保存新版' : '待保存新文件' }}</el-tag></span>
              <el-progress v-if="item.status === 'uploading'" :percentage="item.progress" />
              <small v-else-if="item.status === 'queued'">等待上传</small>
              <small v-else :class="{ 'material-error': item.status === 'failed' }">{{ item.error || '已暂存，等待保存项目' }}</small>
            </div>
            <el-button v-if="item.status === 'failed'" link type="primary" :disabled="disabled" @click="send(item)">重试</el-button>
            <el-button link :disabled="disabled" @click="discard(item)">取消上传</el-button>
          </div>
          <small v-if="!categoryRows(category.key).length && !categoryPending(category.key).length" class="material-hint">暂无文件</small>
      </div>
    </section>
    <div v-if="removed.length" class="material-hint">{{ removed.length }} 个文件将在保存后移除（含全部版本）。<el-button link :disabled="disabled" @click="removed = []">撤销移除</el-button></div>
    <DraggableFormDialog v-model="folderCreatorVisible" :title="folderLevel === 1 ? '新建一级文件夹' : '新建二级文件夹'" width="min(480px, calc(100vw - 32px))" append-to-body class="material-folder-dialog">
      <AppForm ref="folderFormRef" :model="folderForm" :rules="folderRules" label-width="90px" @submit.prevent="confirmFolder">
        <el-form-item v-if="folderLevel === 2" label="一级文件夹" prop="parentId"><el-select v-model="folderForm.parentId" style="width:100%" placeholder="请选择一级文件夹"><el-option v-for="folder in rootFolders" :key="folder.id" :label="folder.name" :value="folder.id" /></el-select></el-form-item>
        <el-form-item label="文件夹名称" prop="name"><el-input v-model="folderForm.name" maxlength="100" show-word-limit placeholder="请输入文件夹名称" @keyup.enter="confirmFolder" /></el-form-item>
        <p class="material-hint">创建后随项目保存生效，取消编辑不会保存文件夹。</p>
      </AppForm>
      <template #footer><el-button @click="folderCreatorVisible = false">取消</el-button><el-button type="primary" :disabled="disabled" @click="confirmFolder">创建</el-button></template>
    </DraggableFormDialog>
    <DraggableFormDialog v-model="historyVisible" title="资料历史版本" width="min(760px, calc(100vw - 32px))" append-to-body>
      <div v-loading="historyLoading" class="material-history">
        <div v-for="row in history" :key="row.id" class="material-row"><div class="material-info"><span>V{{ row.version_no }} · {{ row.original_name }}</span><small>{{ sizeText(row.file_size) }} · {{ row.uploader_name }} · {{ timeText(row.created_at) }}</small></div><el-button link type="primary" @click="download(row)">下载</el-button></div>
      </div>
      <template #footer><el-button @click="historyVisible = false">关闭</el-button></template>
    </DraggableFormDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import AnnotationMaterialExplorer from '@/components/annotation/AnnotationMaterialExplorer.vue'
import * as api from '@/api/annotationMaterials'
import { formatDateTimeMinute } from '@/utils/dateTime'
import { folderNameError, folderParentId, newFolderId, withDefaultProjectFolder } from '@/utils/annotationMaterialFolders'

const props = defineProps({ projectId: { type: String, default: '' }, readonly: Boolean, active: { type: Boolean, default: true }, disabled: Boolean })
const categories = [{ key: 'project', label: '项目资料' }, { key: 'quotation', label: '报价单' }, { key: 'contract', label: '合同' }]
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
const history = ref([]), historyVisible = ref(false), historyLoading = ref(false)
let generation = 0, requestId = 0, nextKey = 0
const sizeText = size => size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(size / 1024)} KB`
// 后端资料时间使用 UTC，显式标记时区后交给公共格式化函数。
const timeText = value => formatDateTimeMinute(value && !/(Z|[+-]\d{2}:\d{2})$/.test(value) ? `${value}Z` : value)
const inCurrentFolder = row => row.category !== 'project' || (row.folder_id || null) === selectedFolderId.value
const categoryRows = category => rows.value.filter(row => row.category === category && inCurrentFolder(row) && !removed.value.includes(row.file_id))
const categoryPending = category => pending.value.filter(item => item.category === category && inCurrentFolder(item))
const hasReplacement = id => pending.value.some(item => item.fileId === id)

async function openFolderCreator(level) {
  if (props.disabled || props.readonly || loading.value || loadError.value) return
  folderLevel.value = level
  folderForm.name = ''; folderForm.parentId = folderParentId(allFolders.value, selectedFolderId.value)
  folderCreatorVisible.value = true
  await nextTick(); folderFormRef.value?.clearValidate()
}
let creatingFolder = false
async function confirmFolder() {
  if (creatingFolder || props.disabled || props.readonly || !folderCreatorVisible.value) return
  creatingFolder = true
  const session = generation
  try {
    const valid = await folderFormRef.value?.validate().catch(() => false)
    if (!valid || session !== generation || !folderCreatorVisible.value) return
    if (allFolders.value.filter(folder => folder.pending || folder.default).length >= 200) { ElMessage.warning('每次保存最多创建200个文件夹'); return }
    const id = newFolderId()
    createdFolders.value.push({ id, parent_id: folderLevel.value === 2 ? folderForm.parentId : null, name: folderForm.name.trim() })
    selectedFolderId.value = id; folderCreatorVisible.value = false
  } finally { creatingFolder = false }
}

async function reload() {
  const serial = ++requestId
  if (!props.projectId) { rows.value = []; savedFolders.value = []; loading.value = false; loadError.value = ''; return }
  loading.value = true; loadError.value = ''
  try {
    const [result, directories] = await Promise.all([api.listMaterials(props.projectId), api.listMaterialFolders(props.projectId)])
    if (serial === requestId) { rows.value = result; savedFolders.value = directories }
  }
  catch (error) { if (serial === requestId) loadError.value = error.detail || '项目资料加载失败' }
  finally { if (serial === requestId) loading.value = false }
}

function release(id) {
  if (id) void api.cancelMaterialUpload(id).catch(() => { /* 断网时由云端24小时过期清理兜底。 */ })
}
function reset() {
  generation += 1; requestId += 1
  pending.value.forEach(item => { item.controller?.abort(); release(item.upload?.id) })
  pending.value = []; removed.value = []; rows.value = []; historyVisible.value = false; loadError.value = ''; loading.value = false
  savedFolders.value = []; createdFolders.value = []; selectedFolderId.value = null; folderCreatorVisible.value = false
  defaultFolderId.value = newFolderId()
}
async function send(item) {
  if (pending.value.filter(row => row !== item && row.status === 'uploading').length >= 3) { item.status = 'queued'; return }
  const session = generation
  item.status = 'uploading'; item.error = ''; item.progress = 0; item.controller = new AbortController()
  try {
    const result = await api.uploadMaterial(item.file, event => { item.progress = Math.min(99, Math.round(event.loaded / (event.total || item.file.size) * 100)) }, item.controller.signal)
    if (session !== generation || !pending.value.includes(item)) { release(result.id); return }
    item.upload = result; item.status = 'ready'; item.progress = 100
  } catch (error) {
    if (session !== generation || !pending.value.includes(item)) return
    item.status = 'failed'; item.error = error.detail || '上传失败，请重试或取消此文件'
  } finally {
    if (session === generation) {
      const next = pending.value.find(row => row.status === 'queued')
      if (next) void send(next)
    }
  }
}
function selectFiles(event, category, fileId = null) {
  const files = Array.from(event.target.files || []); event.target.value = ''
  addFiles(files, category, fileId)
}
function addFiles(files, category, fileId = null) {
  if (props.disabled || props.readonly || loading.value || loadError.value) return
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
function discard(item) { item.controller?.abort(); release(item.upload?.id); pending.value = pending.value.filter(row => row !== item) }
async function remove(row) {
  try { await ElMessageBox.confirm(`保存后将移除“${row.original_name}”及其全部历史版本，无法恢复。是否标记移除？`, '移除项目资料', { type: 'warning' }) } catch { return }
  pending.value.filter(item => item.fileId === row.file_id).forEach(discard)
  removed.value.push(row.file_id)
}
async function download(row) { try { await api.downloadMaterial(props.projectId, row) } catch (error) { ElMessage.error(error.detail || '资料下载失败') } }
async function showHistory(row) {
  historyVisible.value = true; historyLoading.value = true; history.value = []
  try { history.value = await api.listMaterialVersions(props.projectId, row.file_id) }
  catch (error) { ElMessage.error(error.detail || '历史版本加载失败') }
  finally { historyLoading.value = false }
}
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
onBeforeUnmount(reset)
defineExpose({ validate, changes, saved, reload })
</script>

<style scoped>
.material-manager { width: 100%; min-width: 0; }
.material-category { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.material-heading,.material-row,.material-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.material-heading { justify-content: space-between; margin-bottom: 8px; }
.material-row { padding: 8px 0; }
.material-info { flex: 1; min-width: 160px; overflow-wrap: anywhere; }
.material-info small { display: block; color: var(--el-text-color-secondary); margin-top: 4px; }
.material-hint { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.material-upload { color: var(--el-color-primary); cursor: pointer; font-size: 13px; position: relative; }
.material-upload input { position: absolute; inset: 0; width: 100%; opacity: 0; cursor: pointer; }
.material-upload:focus-within { outline: 2px solid var(--el-color-primary); outline-offset: 3px; }
.material-upload.disabled { opacity: .5; cursor: default; }
.material-info .material-error { color: var(--el-color-danger); }
.material-history { max-height: 55vh; overflow-y: auto; }
@media (max-width: 600px) { .material-actions { width: 100%; } }
</style>

<style>
.el-dialog.material-folder-dialog { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
.material-folder-dialog .el-dialog__header,.material-folder-dialog .el-dialog__footer { flex-shrink: 0; }
.material-folder-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.material-folder-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); }
</style>
