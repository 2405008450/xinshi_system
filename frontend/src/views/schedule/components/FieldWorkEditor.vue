<template>
  <DraggableFormDialog v-model="visible" :title="title" class="field-work-dialog" width="min(820px, calc(100vw - 32px))"
    top="5vh" :close-on-click-modal="false" :before-close="beforeClose" @closed="$emit('close')">
    <template #header>
      <DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="title"
        :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" />
    </template>
    <div ref="body">
      <el-alert v-if="optionsError" :title="optionsError" type="error" :closable="false"><el-button link @click="loadOptions">重试</el-button></el-alert>
      <AppForm ref="form" :model="draft" :rules="rules" label-position="top" :disabled="saving" :saved-sync-enabled="false" data-screenshot-editor="own">
        <el-form-item label="外勤类型" prop="type_path">
          <el-cascader v-model="draft.type_path" :options="categories" :disabled="optionsLoading" placeholder="选择外勤类型" />
        </el-form-item>
        <div class="field-work-grid">
          <el-form-item label="开始时间（UTC+8）" prop="start_at">
            <el-date-picker v-model="draft.start_at" type="datetime" value-format="YYYY-MM-DD HH:mm" format="YYYY-MM-DD HH:mm" />
          </el-form-item>
          <el-form-item label="结束时间（UTC+8）" prop="end_at">
            <el-date-picker v-model="draft.end_at" type="datetime" value-format="YYYY-MM-DD HH:mm" format="YYYY-MM-DD HH:mm" />
          </el-form-item>
        </div>
        <el-form-item label="地点" prop="location">
          <el-input v-model.trim="draft.location" maxlength="255" placeholder="填写外勤地点" />
        </el-form-item>
        <el-form-item label="陪同人" prop="companion_ids">
          <el-select v-model="draft.companion_ids" multiple filterable clearable :loading="optionsLoading" placeholder="搜索姓名或账号，可多选">
            <el-option v-for="person in people" :key="person.id" :value="person.id" :label="personLabel(person)" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isCustomer" label="客户名称" prop="customer">
          <div class="field-work-inline">
            <el-select v-model="draft.customer" filterable clearable allow-create default-first-option
              :remote="canReadClients" :remote-method="searchClients" :loading="clientsLoading"
              placeholder="搜索客户，也可直接填写名称" @visible-change="visible => visible && searchClients('')">
              <el-option v-for="client in clientOptions" :key="client.id" :value="client.id" :label="client.client_name">
                <span>{{ client.client_name }}</span><small v-if="client.client_code"> · {{ client.client_code }}</small>
              </el-option>
            </el-select>
            <el-button v-if="canCreateClient" @click="openNewClient">新增客户信息</el-button>
          </div>
          <span v-if="clientLookupError" class="field-work-error">{{ clientLookupError }}</span>
        </el-form-item>
        <el-form-item label="外勤打卡照片" prop="photo">
          <div class="field-work-photo-editor" tabindex="0" aria-label="上传或粘贴外勤打卡照片" @paste="pastePhoto">
            <el-upload accept="image/jpeg,image/png,image/webp" :auto-upload="false" :show-file-list="false"
              :on-change="file => selectPhoto(file.raw)">
              <el-button>{{ draft.photo || previewUrl || (record?.has_photo && !draft.remove_photo) ? '更换照片' : '上传照片' }}</el-button>
            </el-upload>
            <el-button v-if="draft.photo || (record?.has_photo && !draft.remove_photo)" link type="danger" @click="removePhoto">移除照片</el-button>
            <span v-if="photoError" class="field-work-error">{{ photoError }}</span>
            <img v-if="previewUrl" :src="previewUrl" alt="外勤照片预览">
          </div>
        </el-form-item>
        <el-form-item label="补充说明" prop="notes">
          <el-input v-model="draft.notes" type="textarea" :rows="3" maxlength="4000" show-word-limit />
        </el-form-item>
        <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      </AppForm>
    </div>
    <template #footer>
      <el-button :disabled="saving" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!categories.length" @click="save">保存</el-button>
    </template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="newClientVisible" title="新增客户信息" width="min(500px, calc(100vw - 32px))"
    :close-on-click-modal="false" :before-close="closeNewClient">
    <AppForm ref="clientForm" :model="newClient" :rules="clientRules" label-position="top" :disabled="clientSaving" :saved-sync-enabled="false">
      <el-form-item label="客户全称" prop="client_name"><el-input v-model.trim="newClient.client_name" maxlength="255" /></el-form-item>
      <el-form-item label="客户简称" prop="client_short_name"><el-input v-model.trim="newClient.client_short_name" maxlength="100" /></el-form-item>
      <el-alert v-if="clientSaveError" :title="clientSaveError" type="error" :closable="false" />
    </AppForm>
    <template #footer>
      <el-button :disabled="clientSaving" @click="newClientVisible = false">取消</el-button>
      <el-button type="primary" :loading="clientSaving" @click="saveClient">保存客户</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import { createClient, getClientOptions } from '@/api/clients'
import { getFieldWorkOptions, getFieldWorkPhoto, saveFieldWork } from '@/api/fieldWork'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { hasPermission } from '@/utils/permission'
import { newFolderId } from '@/utils/annotationMaterialFolders'

const props = defineProps({ record: Object })
const emit = defineEmits(['close', 'saved'])
const title = props.record ? '编辑外勤' : '新增外勤'
const visible = ref(true)
const body = ref()
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(body)
const form = ref()
const saving = ref(false)
const saveError = ref('')
const record = props.record
const recordId = record?.id || newFolderId()
const draft = reactive({
  type_path: record?.type_path || [],
  start_at: businessDateTimeInputValue(record?.start_at).slice(0, 16),
  end_at: record ? businessDateTimeInputValue(record.end_at).slice(0, 16) : '',
  location: record?.location || '',
  companion_ids: record?.companions.map(person => person.id) || [],
  customer: record?.client_id || record?.client_name || '',
  notes: record?.notes || '',
  photo: null,
  remove_photo: false,
})
const isCustomer = computed(() => draft.type_path?.[0] === 'customer')
const required = (message, trigger = 'change') => ({ required: true, message, trigger })
const isoTime = value => value ? `${value.replace(' ', 'T')}:00+08:00` : null
const rules = {
  type_path: [{ ...required('请选择外勤类型'), type: 'array', min: 1 }],
  start_at: [required('请选择开始时间')],
  end_at: [required('请选择结束时间'), {
    validator: (_rule, value, done) => done(
      draft.start_at && value && value <= draft.start_at ? new Error('结束时间必须晚于开始时间') : undefined,
    ),
    trigger: 'change',
  }],
  location: [required('请填写地点', 'blur')],
  customer: [required('请选择或填写客户名称')],
}

const categories = ref([])
const people = ref(record?.companions || [])
const optionsLoading = ref(false)
const optionsError = ref('')
const lifecycle = new AbortController()
const personLabel = person => person.name === person.username ? person.name : `${person.name}（${person.username}）`

async function loadOptions() {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    const data = await getFieldWorkOptions(lifecycle.signal)
    if (lifecycle.signal.aborted) return
    categories.value = data.categories
    const active = new Set(data.people.map(person => person.id))
    people.value = [...data.people, ...(record?.companions || []).filter(person => !active.has(person.id))]
  } catch (reason) {
    if (!lifecycle.signal.aborted) optionsError.value = reason.detail || '读取外勤选项失败'
  } finally {
    optionsLoading.value = false
  }
}

const canReadClients = hasPermission('clients:read')
const canCreateClient = hasPermission('clients:write')
const knownClients = new Map()
if (record?.client_id) knownClients.set(record.client_id, { id: record.client_id, client_name: record.client_name })
const clientOptions = shallowRef([...knownClients.values()])
const clientsLoading = ref(false)
const clientLookupError = ref('')
let clientController

async function searchClients(keyword) {
  if (!canReadClients) return
  clientController?.abort()
  const controller = new AbortController()
  clientController = controller
  clientsLoading.value = true
  clientLookupError.value = ''
  try {
    const values = await getClientOptions({ keyword, limit: 50 }, { signal: controller.signal })
    if (controller.signal.aborted) return
    for (const client of values) knownClients.set(client.id, client)
    const selected = knownClients.get(draft.customer)
    clientOptions.value = selected && !values.some(client => client.id === selected.id) ? [selected, ...values] : values
  } catch (reason) {
    if (!controller.signal.aborted) clientLookupError.value = reason.detail || '查询客户失败'
  } finally {
    if (clientController === controller) clientsLoading.value = false
  }
}

const newClientVisible = ref(false)
const newClient = reactive({ client_name: '', client_short_name: '' })
const clientRules = {
  client_name: [required('请填写客户全称', 'blur')],
  client_short_name: [required('请填写客户简称', 'blur')],
}
const clientForm = ref()
const clientSaving = ref(false)
const clientSaveError = ref('')

function openNewClient() {
  Object.assign(newClient, {
    client_name: knownClients.has(draft.customer) ? '' : draft.customer || '',
    client_short_name: '',
  })
  clientSaveError.value = ''
  newClientVisible.value = true
}

function closeNewClient(done) {
  if (!clientSaving.value) done()
}

async function saveClient() {
  if (clientSaving.value) return
  clientSaving.value = true
  clientSaveError.value = ''
  try {
    if (!await clientForm.value.validate().catch(() => false)) return
    const client = await createClient({ ...newClient })
    knownClients.set(client.id, client)
    clientOptions.value = [client, ...clientOptions.value.filter(option => option.id !== client.id)]
    draft.customer = client.id
    newClientVisible.value = false
  } catch (reason) {
    clientSaveError.value = reason.detail || '保存客户失败'
  } finally {
    clientSaving.value = false
  }
}

const previewUrl = ref('')
const photoError = ref('')

function setPreview(file) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = file ? URL.createObjectURL(file) : ''
}

function selectPhoto(file) {
  if (!file || saving.value) return
  photoError.value = ''
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 20 * 1024 * 1024) {
    photoError.value = '请选择不超过 20 MB 的 PNG、JPEG 或 WebP 图片'
    return
  }
  draft.photo = file
  draft.remove_photo = false
  setPreview(file)
}

function pastePhoto(event) {
  const file = [...(event.clipboardData?.files || [])].find(file => file.type.startsWith('image/'))
  if (file) {
    event.preventDefault()
    selectPhoto(file)
  }
}

function removePhoto() {
  draft.photo = null
  draft.remove_photo = true
  photoError.value = ''
  setPreview(null)
}

function beforeClose(done) {
  if (!saving.value && !clientSaving.value) done()
}

async function save() {
  if (saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    if (!await form.value.validate().catch(() => false)) return
    const client = isCustomer.value ? knownClients.get(draft.customer) : null
    await saveFieldWork({
      id: recordId, revision: record?.revision || 0, type_path: draft.type_path,
      start_at: isoTime(draft.start_at), end_at: isoTime(draft.end_at), location: draft.location,
      companion_ids: draft.companion_ids, client_id: client?.id || null,
      client_name: isCustomer.value && !client ? draft.customer.trim() : null,
      notes: draft.notes, remove_photo: draft.remove_photo,
    }, draft.photo)
    emit('saved')
  } catch (reason) {
    saveError.value = reason.detail || '保存外勤失败'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  loadOptions()
  if (!record?.has_photo) return
  try {
    const blob = await getFieldWorkPhoto(record.id, false, lifecycle.signal)
    if (!lifecycle.signal.aborted && !draft.photo && !draft.remove_photo) setPreview(blob)
  } catch {
    if (!lifecycle.signal.aborted && !draft.photo && !draft.remove_photo) photoError.value = '原照片预览加载失败'
  }
})
onBeforeUnmount(() => {
  lifecycle.abort()
  clientController?.abort()
  setPreview(null)
})
</script>

<style scoped>
.field-work-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.field-work-grid :deep(.el-date-editor), .el-cascader { width: 100%; }
.field-work-inline, .field-work-photo-editor { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; width: 100%; }
.field-work-inline .el-select { flex: 1 1 200px; }
.field-work-photo-editor img { flex-basis: 100%; width: min(100%, 420px); max-height: 220px; object-fit: contain; object-position: left; }
.field-work-error { color: var(--el-color-danger); }
:global(.field-work-dialog) { display: flex; flex-direction: column; overflow: hidden; max-height: 90vh; }
:global(.field-work-dialog .el-dialog__header), :global(.field-work-dialog .el-dialog__footer) { flex-shrink: 0; }
:global(.field-work-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.field-work-dialog .el-dialog__footer) { border-top: 1px solid var(--el-border-color-lighter); }
@media (max-width: 620px) { .field-work-grid { grid-template-columns: 1fr; gap: 0; } }
</style>
