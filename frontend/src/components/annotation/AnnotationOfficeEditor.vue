<template>
  <OfficeEditorSurface :standalone="standalone" :open="state.open" :before-close="beforeClose" @close="finish(false)">
    <template #header><div class="office-title"><strong>{{ creating ? `新建 ${officeLabel}` : '在线编辑' }}</strong>
      <span class="office-title__name" @mousedown.stop>{{ fileName }}</span>
      <el-tag v-if="session?.mode === 'view'" type="info" size="small">只读</el-tag>
    </div></template>
    <div v-loading="loading || saving" class="office-body" :element-loading-text="saving ? '正在保存，请稍候…' : `正在打开 ${officeLabel}…`">
      <AppForm v-if="creating && !session" ref="formRef" :model="form" :rules="rules" label-width="80px" @submit.prevent="open">
        <el-form-item label="文件名称" prop="name"><el-input v-model="form.name" maxlength="250" placeholder="请输入文件名称，扩展名自动补充" :disabled="loading"><template #append>.{{ kind }}</template></el-input></el-form-item>
        <p class="office-hint">保存到“{{ request.create.folderName }}”。填写名称后点击“开始编辑”。</p>
      </AppForm>
      <el-alert v-if="session?.mode === 'view'" type="info" :closable="false" show-icon
        :title="session.occupant ? `${session.occupant} 正在编辑，当前显示已保存版本；关闭后重新打开可重试取得编辑权限。` : '当前账号仅可查看此文档。'" />
      <el-alert v-else-if="session" type="info" :closable="false" title="修改先暂存在文档服务，点击底部保存按钮后才生成资料版本；取消将放弃本次修改。" />
      <el-alert v-if="error" type="error" :closable="false" show-icon :title="error">
        <el-button v-if="!dirty && !saving" link type="primary" @click="open">重新加载</el-button>
        <el-button v-if="request.file" link type="primary" @click="download">下载已保存版本</el-button>
      </el-alert>
      <div class="office-frame" :inert="saving || expired || undefined"><div :id="hostId" /></div>
    </div>
    <template #footer>
      <span class="office-status">{{ expired ? '会话已失效，请重新打开' : syncing ? '正在同步修改到文档服务…' : dirty ? '有未保存的修改' : session?.mode === 'view' ? '只读查看' : '保存后生成新版本，原文件保留' }}</span>
      <el-button :disabled="saving" @click="requestClose">{{ session?.mode === 'view' ? '关闭' : '取消' }}</el-button>
      <el-button v-if="session?.mode !== 'view'" type="primary" :loading="saving || loading"
        :disabled="expired || syncing || (!!session && !ready)" @click="session ? save() : open()">{{ !session && creating ? '开始编辑' : creating ? '保存文件' : '保存为新版本' }}</el-button>
    </template>
  </OfficeEditorSurface>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import OfficeEditorSurface from './OfficeEditorSurface.vue'
import AppForm from '@/components/common/AppForm.vue'
import { useMaterialEditor } from '@/composables/useMaterialEditor'
import { documentFileName, documentNameError, onlineEditKind } from '@/utils/materialDocument'
import { loadOfficeScript } from '@/utils/officeScript'
import { newFolderId } from '@/utils/annotationMaterialFolders'
import * as api from '@/api/annotationMaterials'

const props = defineProps({ standalone: Boolean, editorRequest: Object })
const emit = defineEmits(['close'])
const { state, closeMaterialEditor, notifyMaterialSaved } = useMaterialEditor()
const request = computed(() => props.editorRequest || state.request)
function finish(saved, versionId) { if (props.standalone) emit('close', { saved, versionId }); else closeMaterialEditor() }
const creating = computed(() => Boolean(request.value?.create))
const kind = computed(() => request.value?.create?.kind || onlineEditKind(request.value?.file?.original_name))
const officeLabel = computed(() => kind.value === 'xlsx' ? 'Excel' : 'Word')
const form = reactive({ name: '' }), formRef = ref(null)
const rules = { name: [{ validator: (_rule, value, done) => {
  const message = documentNameError(value, kind.value, request.value?.create?.siblingNames || [])
  done(message ? new Error(message) : undefined)
}, trigger: 'blur' }] }
const fileName = computed(() => request.value?.file?.original_name || (form.name.trim() ? documentFileName(form.name, kind.value) : `未命名.${kind.value}`))
const session = ref(null), error = ref(''), loading = ref(false), saving = ref(false), ready = ref(false)
const dirty = ref(false), syncing = ref(false), expired = ref(false)
const hostId = `material-office-${newFolderId()}`
let docEditor, heartbeat, serial = 0, revision = 0, destroyed = false, leaseDeadline = 0, readyTimeout, pollTimer, pendingPoll
const errorText = value => value?.detail || value?.message || 'Office 服务暂不可用，请重试'

function stopEditor() {
  window.clearInterval(heartbeat); window.clearTimeout(readyTimeout)
  docEditor?.destroyEditor(); docEditor = null
  ready.value = false
}
function loseLease(message) {
  expired.value = true; ready.value = false
  error.value = message || '无法续租编辑会话，已停止编辑，请关闭后重新打开'
}
async function tick() {
  if (!session.value || expired.value || destroyed) return
  try {
    await api.heartbeatOfficeSession(session.value.id)
    leaseDeadline = Date.now() + 110000
  } catch (failure) {
    if (failure.response?.status === 409 || failure.response?.status === 403 || Date.now() >= leaseDeadline) loseLease(errorText(failure))
    else error.value = '文档服务连接暂时中断，正在重试；请保持窗口打开'
  }
}

async function open() {
  if (loading.value || saving.value) return
  if (creating.value && !session.value && !await formRef.value?.validate().catch(() => false)) return
  const current = ++serial
  loading.value = true; error.value = ''; expired.value = false
  try {
    if (session.value) await api.discardOfficeSession(session.value.id)
    stopEditor(); session.value = null; revision = 0
    const result = await api.openOfficeSession(request.value.projectId, creating.value
      ? { name: fileName.value, folder_id: request.value.create.folderId || null }
      : { file_id: request.value.file.file_id })
    if (destroyed || current !== serial) { void api.discardOfficeSession(result.id).catch(() => {}); return }
    session.value = result
    leaseDeadline = Date.now() + 110000
    heartbeat = window.setInterval(tick, 30000)
    const sdk = await loadOfficeScript(result.script_url)
    if (destroyed || current !== serial) return
    await nextTick()
    const config = { ...result.config, events: {
      onDocumentReady: () => { if (destroyed || current !== serial) return; window.clearTimeout(readyTimeout); ready.value = true; loading.value = false },
      onDocumentStateChange: event => {
        if (destroyed || current !== serial || result.mode === 'view') return
        syncing.value = Boolean(event.data)
        if (event.data) { dirty.value = true; revision++ }
      },
      onError: () => { if (destroyed || current !== serial) return; loading.value = false; error.value = `${officeLabel.value} 编辑器发生错误，请保留当前内容后重试；原文件未改变` },
      onRequestClose: () => { if (!destroyed && current === serial) void requestClose() },
    } }
    docEditor = new sdk.DocEditor(hostId, config)
    if (!ready.value) readyTimeout = window.setTimeout(() => { loading.value = false; error.value = `${officeLabel.value} 文件打开超时，请检查文档服务连接` }, 45000)
  } catch (failure) { error.value = errorText(failure); loading.value = false }
}

function delay() {
  return new Promise(resolve => { pendingPoll = resolve; pollTimer = window.setTimeout(() => { pendingPoll = null; resolve() }, 1000) })
}
async function save() {
  if (!session.value || !ready.value || syncing.value || expired.value || saving.value) return
  saving.value = true; error.value = ''
  const projectId = request.value.projectId, id = session.value.id, saveId = newFolderId()
  try {
    let result
    try { result = await api.saveOfficeSession(id, saveId, revision) }
    catch (failure) {
      // 命令超时不代表保存未发生，先查询持久化任务，再决定是否重试。
      result = await api.officeSessionStatus(id)
      if (result.save_id !== saveId) throw failure
    }
    for (let i = 0; i < 70 && result.save_state === 'pending' && !destroyed; i++) {
      await delay()
      if (!destroyed) result = await api.officeSessionStatus(id)
    }
    if (destroyed) return
    if (result.save_state !== 'complete') throw new Error(result.error || '保存尚未完成，请保留窗口后重试')
    dirty.value = false; notifyMaterialSaved(projectId)
    ElMessage.success(creating.value ? `${officeLabel.value} 文件已保存` : `${officeLabel.value} 文件已保存，历史版本保留`)
    finish(true, result.version_id)
  } catch (failure) { error.value = errorText(failure) }
  finally { saving.value = false }
}
async function discard() {
  if (session.value) await api.discardOfficeSession(session.value.id)
  dirty.value = false; finish(false)
}
async function confirmClose() {
  if (saving.value) return false
  if (dirty.value || (creating.value && form.name.trim())) {
    try { await ElMessageBox.confirm('当前修改尚未保存，关闭后将丢失。是否放弃修改？', '放弃修改', { type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑' }) }
    catch { return false }
  }
  try { await discard(); return true }
  catch (failure) { error.value = errorText(failure); return false }
}
async function beforeClose(done) { if (await confirmClose()) done() }
async function requestClose() { await confirmClose() }
async function download() { try { await api.downloadMaterial(request.value.projectId, request.value.file) } catch (failure) { ElMessage.error(errorText(failure)) } }
function beforeUnload(event) { if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(() => props.standalone ? confirmClose() : true)
onBeforeRouteUpdate(() => props.standalone ? confirmClose() : true)
function pageHide(event) {
  // 关闭标签页时普通异步请求可能被取消，keepalive 尽快释放锁；断网仍由租约兜底。
  if (!event.persisted && session.value && !saving.value) api.releaseOfficeSessionOnExit(session.value.id)
}
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); window.addEventListener('pagehide', pageHide); if (!creating.value) void open() })
onBeforeUnmount(() => {
  destroyed = true; serial++; stopEditor(); window.clearTimeout(pollTimer); pendingPoll?.()
  window.removeEventListener('beforeunload', beforeUnload)
  window.removeEventListener('pagehide', pageHide)
  if (session.value) void api.discardOfficeSession(session.value.id).catch(() => {})
})
</script>

<style scoped>
.office-title { display: flex; align-items: center; gap: 8px; padding-right: 32px; min-width: 0; }
.office-title__name { user-select: text; cursor: text; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.office-body { display: flex; flex-direction: column; gap: 8px; min-height: 0; height: 100%; }
.office-frame { flex: 1; min-height: 300px; height: 65vh; }
.office-frame > div { height: 100%; }
.office-status { margin-right: auto; color: var(--el-text-color-secondary); font-size: 12px; }
.office-hint { color: var(--el-text-color-secondary); font-size: 12px; }
.office-editor-page .office-frame { height: auto; min-height: 0; }
.office-editor-page .office-body > .el-alert { flex-shrink: 0; border-radius: 0; padding: 4px 12px; }
.office-editor-page .office-body { gap: 0; }
.office-editor-page .el-form { padding: 12px; }
</style>
<style>
.el-dialog.material-office-dialog { display: flex; flex-direction: column; height: 90vh; max-height: 90vh; overflow: hidden; }
.material-office-dialog .el-dialog__header,.material-office-dialog .el-dialog__footer { flex-shrink: 0; }
.material-office-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.material-office-dialog .el-dialog__footer { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; border-top: 1px solid var(--el-border-color-lighter); background: #f8fafc; }
@media (max-width: 600px) {
  .material-office-dialog .el-dialog__footer { justify-content: flex-end; }
  .material-office-dialog .office-status,.office-editor-page .office-status { flex-basis: 100%; margin-right: 0; text-align: left; }
}
</style>
