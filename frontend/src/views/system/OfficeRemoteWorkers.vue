<template>
  <el-card class="remote-workers" shadow="never">
    <template #header>
      <div class="remote-workers-header">
        <h3>居家办公人员</h3>
        <div v-if="canWrite" class="remote-workers-actions">
          <el-button v-if="!deleteMode" type="primary" :disabled="loading || editing" @click="edit()">新增人员</el-button>
          <BatchDeleteToolbar
            v-if="!editing && rows.length"
            :active="deleteMode"
            :selected-count="selectedRows.length"
            :loading="deleting"
            @enter="enterDeleteMode"
            @exit="exitDeleteMode"
            @confirm="confirmBatchDelete"
          />
        </div>
      </div>
    </template>

    <AppForm v-if="editing" ref="formRef" :model="form" :rules="rules" label-position="top" class="remote-workers-form">
      <el-form-item label="城市" prop="city">
        <el-select v-model="form.city" filterable allow-create default-first-option clearable :disabled="saving" placeholder="选择或输入城市">
          <el-option v-for="city in cityOptions" :key="city" :label="city" :value="city" />
        </el-select>
      </el-form-item>
      <el-form-item label="人员" prop="user_id">
        <el-select v-model="form.user_id" filterable clearable :loading="loadingPeople" :disabled="saving" placeholder="搜索全体人员">
          <el-option v-for="person in people" :key="person.id" :label="personLabel(person)" :value="person.id" />
        </el-select>
      </el-form-item>
      <div class="remote-workers-actions">
        <el-button :disabled="saving" @click="cancelEdit">取消</el-button>
        <el-button type="primary" :disabled="loadingPeople" :loading="saving" @click="save">保存</el-button>
      </div>
    </AppForm>

    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="load">重新加载</el-button>
    </el-alert>
    <el-alert v-if="editing && formError" :title="formError" type="error" :closable="false" />
    <el-table ref="tableRef" v-loading="loading" :data="rows" row-key="id" empty-text="暂无居家办公人员" @selection-change="handleDeleteSelectionChange">
      <el-table-column v-if="deleteMode" type="selection" width="48" />
      <el-table-column prop="city" label="城市" min-width="120" />
      <el-table-column label="人员" min-width="160">
        <template #default="{ row }">{{ row.name }}<span v-if="!row.is_active">（停用）</span></template>
      </el-table-column>
      <el-table-column v-if="canWrite && !deleteMode" label="操作" width="100" fixed="right">
        <template #default="{ row }"><el-button link type="primary" :disabled="editing" @click="edit(row)">编辑</el-button></template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { createRemoteWorker, deleteRemoteWorker, getRemoteWorkerPeople, getRemoteWorkers, updateRemoteWorker } from '@/api/offices'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({ cities: { type: Array, default: () => [] }, canWrite: Boolean })
const rows = ref([])
const people = ref([])
const tableRef = ref()
const formRef = ref()
const editing = ref(false)
const loading = ref(false)
const loadingPeople = ref(false)
const saving = ref(false)
const error = ref('')
const formError = ref('')
const form = reactive({ id: '', city: '', user_id: '', revision: 0 })
const rules = {
  city: [{ required: true, whitespace: true, max: 100, message: '请选择或填写城市（最多100字）', trigger: 'change' }],
  user_id: [{ required: true, message: '请选择人员', trigger: 'change' }],
}
const cityOptions = computed(() => [...new Set([
  ...props.cities.map(item => item.city),
  ...rows.value.map(item => item.city),
])])
const personLabel = person => `${person.name}${person.username !== person.name ? `（${person.username}）` : ''}${person.is_active ? '' : '（停用）'}`

let controller, peopleController
async function load() {
  controller?.abort()
  const request = new AbortController()
  controller = request
  loading.value = true
  error.value = ''
  try {
    const result = await getRemoteWorkers({ signal: request.signal })
    if (!request.signal.aborted) rows.value = result.items
  } catch (failure) {
    if (!request.signal.aborted) error.value = getLocalizedErrorMessage(failure, '读取居家办公人员失败')
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

async function edit(row) {
  Object.assign(form, { id: '', city: '', user_id: '', revision: 0 }, row)
  formError.value = ''
  editing.value = true
  loadingPeople.value = true
  peopleController?.abort()
  const request = new AbortController()
  peopleController = request
  try {
    const result = await getRemoteWorkerPeople({ signal: request.signal })
    if (!request.signal.aborted) people.value = result.items
  } catch (failure) {
    if (!request.signal.aborted) formError.value = getLocalizedErrorMessage(failure, '读取人员列表失败，请重新打开编辑')
  } finally {
    if (!request.signal.aborted) loadingPeople.value = false
  }
}

function cancelEdit() {
  peopleController?.abort()
  editing.value = false
}

async function save() {
  if (saving.value || loadingPeople.value) return
  saving.value = true
  formError.value = ''
  try {
    if (!await formRef.value.validate().catch(() => false)) return
    const data = { city: form.city.trim(), user_id: form.user_id }
    const result = form.id
      ? await updateRemoteWorker(form.id, { ...data, revision: form.revision })
      : await createRemoteWorker(data)
    ElMessage.success(result.message)
    editing.value = false
    await load()
  } catch (failure) {
    formError.value = getLocalizedErrorMessage(failure, '保存居家办公人员失败')
  } finally {
    saving.value = false
  }
}

const { deleteMode, deleting, selectedRows, enterDeleteMode, exitDeleteMode, handleDeleteSelectionChange, confirmBatchDelete } = useBatchDelete({
  rows, tableRef, reload: load,
  deleteRow: row => deleteRemoteWorker(row.id, row.revision),
  getLabel: row => `${row.name}（${row.city}）`,
  entityName: '居家办公人员登记',
})

onMounted(load)
onBeforeUnmount(() => {
  controller?.abort()
  peopleController?.abort()
})
</script>

<style scoped>
.remote-workers { margin-top: 24px; }
.remote-workers-header, .remote-workers-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.remote-workers-header { justify-content: space-between; }
.remote-workers-header h3 { margin: 0; font-size: 16px; }
.remote-workers-form { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
.remote-workers-form :deep(.el-form-item) { flex: 1 1 220px; margin-bottom: 0; }
.remote-workers-form :deep(.el-select) { width: 100%; }
.remote-workers-actions :deep(.el-button + .el-button) { margin-left: 0; }
</style>
