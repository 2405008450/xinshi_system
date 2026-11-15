<template>
  <DraggableFormDialog
    :model-value="true" class="collection-account-dialog" data-auto-draft="off"
    title="收款账户管理" width="min(760px, calc(100vw - 32px))" top="5vh"
    :before-close="close" :close-on-click-modal="false"
  >
    <template #header>
      <DialogFieldSearchHeader v-if="ready" ref="fieldSearchRef" v-model="fieldSearchKeyword"
        title="收款账户管理" :fetch-suggestions="fetchFieldSuggestions"
        @select="locateDialogField" @clear="clearFieldSearch" />
      <span v-else class="el-dialog__title">收款账户管理</span>
    </template>
    <div ref="body" v-loading="loading||saving">
      <el-alert v-if="localEnvironment" title="请在正式线上系统维护收款账户和附件。" type="info" :closable="false" />
      <el-alert v-else-if="!canWrite" title="当前账号没有管理收款账户的权限。" type="info" :closable="false" />
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <AppForm v-if="ready" :model="draft" :disabled="saving" label-position="top">
        <p>账户信息与对账单设置共用。备注、截图和附件仅在此处查看。</p>
        <el-form-item label="开户行" prop="bank_name">
          <el-input v-model="draft.bank_name" maxlength="255" />
        </el-form-item>
        <el-form-item label="账户名" prop="account_name">
          <el-input v-model="draft.account_name" maxlength="255" />
        </el-form-item>
        <el-form-item label="银行账号" prop="account_number">
          <el-input v-model="draft.account_number" maxlength="100" />
        </el-form-item>
        <el-form-item label="账户备注及附件" prop="notes">
          <div class="collection-materials" data-screenshot-editor="own" @dragover.prevent @drop.prevent="dropFiles" @paste="pasteFiles">
            <el-input v-model="draft.notes" type="textarea" :rows="3" maxlength="5000" show-word-limit
              placeholder="填写备注、粘贴截图，或将文件拖入此处" />
            <div class="collection-upload">
              <el-button :loading="reading" @click="fileInput.click()">上传截图或文件</el-button>
              <small>最多 9 个附件，合计不超过 8 MB。</small>
              <input ref="fileInput" type="file" multiple hidden @change="chooseFiles" />
            </div>
            <ul v-if="draft.attachments.length" class="collection-files">
              <li v-for="(file,index) in draft.attachments" :key="index">
                <el-button link type="primary" @click="download(file)">{{ file.name }}</el-button>
                <el-button link type="danger" :disabled="reading" :aria-label="'移除 '+file.name"
                  @click="draft.attachments.splice(index,1)">移除</el-button>
              </li>
            </ul>
          </div>
        </el-form-item>
      </AppForm>
    </div>
    <template #footer>
      <el-button :disabled="saving" @click="close()">关闭</el-button>
      <el-button v-if="ready" type="primary" :loading="saving" :disabled="reading || !dirty" @click="save">
        保存收款账户
      </el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed, onMounted, reactive, ref} from 'vue'
import {ElMessage, ElMessageBox} from 'element-plus'
import api from '@/api'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import DraggableFormDialog from './DraggableFormDialog.vue'

const emit = defineEmits(['close'])
const endpoint = '/finance/collection-account'
const localEnvironment = import.meta.env.DEV || ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
const canWrite = hasPermission('clients:write')
const body = ref()
const fileInput = ref()
const loading = ref(false)
const saving = ref(false)
const reading = ref(false)
const ready = ref(false)
const error = ref('')
const draft = reactive({revision:0, bank_name:'', account_name:'', account_number:'', notes:'', attachments:[]})
const original = ref(null)
const dirty = computed(() => original.value && (
  ['bank_name','account_name','account_number','notes'].some(key => draft[key] !== original.value[key]) ||
  draft.attachments.length !== original.value.attachments.length ||
  draft.attachments.some((file, index) => file.name !== original.value.attachments[index].name ||
    file.content !== original.value.attachments[index].content)
))
const {fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch} = useDialogFieldSearch(body)

onMounted(async () => {
  if (localEnvironment || !canWrite) return
  loading.value = true
  try {
    original.value = await api.get(endpoint)
    Object.assign(draft, original.value, {attachments:[...original.value.attachments]})
    ready.value = true
  } catch (e) {
    error.value = getLocalizedErrorMessage(e, '收款账户加载失败')
  } finally {
    loading.value = false
  }
})

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve({name:file.name, content:reader.result.split(',')[1]})
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function attach(files) {
  if (saving.value || reading.value || !files.length) return
  const storedBytes = draft.attachments.reduce((sum, file) => sum + file.content.length * 3 / 4 -
    (file.content.match(/=+$/)?.[0].length || 0), 0)
  const incomingBytes = files.reduce((sum, file) => sum + file.size, 0)
  if (draft.attachments.length + files.length > 9 || storedBytes + incomingBytes > 8_000_000) {
    ElMessage.warning('最多 9 个附件，合计不超过 8 MB。')
    return
  }
  if (files.some(file => !file.size || file.name.length > 255)) {
    ElMessage.warning('附件须有内容，文件名不能超过 255 字。')
    return
  }
  reading.value = true
  try {
    draft.attachments.push(...await Promise.all(files.map(readFile)))
  } catch {
    ElMessage.error('附件读取失败，请重试。')
  } finally {
    reading.value = false
  }
}

function chooseFiles(event) {
  void attach([...event.target.files])
  event.target.value = ''
}

function dropFiles(event) {
  void attach([...event.dataTransfer.files])
}

function pasteFiles(event) {
  const files = [...event.clipboardData.files]
  if (!files.length) return
  event.preventDefault()
  void attach(files)
}

function download(file) {
  const bytes = Uint8Array.from(atob(file.content), char => char.charCodeAt(0))
  const url = URL.createObjectURL(new Blob([bytes], {type:'application/octet-stream'}))
  const link = document.createElement('a')
  link.href = url
  link.download = file.name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function save() {
  if (saving.value || reading.value || !ready.value || !dirty.value) return
  saving.value = true
  error.value = ''
  try {
    await api.put(endpoint, {...draft})
    ElMessage.success('收款账户已保存')
    emit('close')
  } catch (e) {
    error.value = getLocalizedErrorMessage(e, '收款账户保存失败')
  } finally {
    saving.value = false
  }
}

async function close(done) {
  if (saving.value || reading.value) return
  if (dirty.value) {
    try {
      await ElMessageBox.confirm('收款账户有未保存的修改，是否放弃？', '关闭收款账户管理', {
        confirmButtonText:'放弃修改', cancelButtonText:'继续编辑',
      })
    } catch { return }
  }
  if (typeof done === 'function') done()
  emit('close')
}
</script>

<style scoped>
.collection-materials { width: 100%; }
.collection-upload, .collection-files li { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
.collection-files { padding: 0; margin: 0; list-style: none; }
.collection-files :deep(.el-button span) { white-space: normal; overflow-wrap: anywhere; }
.collection-upload small { color: var(--el-text-color-secondary); }
:global(.collection-account-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.collection-account-dialog > .el-dialog__header), :global(.collection-account-dialog > .el-dialog__footer) { flex: none; }
:global(.collection-account-dialog > .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.collection-account-dialog > .el-dialog__footer) { border-top: 1px solid var(--el-border-color); }
</style>
