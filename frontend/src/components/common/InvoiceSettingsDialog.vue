<template>
  <DraggableFormDialog :model-value="true" title="财务设置 · 开票接收人" width="min(620px, calc(100vw - 32px))"
    append-to-body :close-on-click-modal="false" :before-close="close">
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <AppForm v-if="settings" :model="form" label-position="top">
        <el-form-item label="开票接收人">
          <el-select v-model="form.userIds" multiple filterable :disabled="!canEdit" style="width:100%" aria-label="开票接收人">
            <el-option-group v-for="group in groups" :key="group.label" :label="group.label">
              <el-option v-for="person in group.users" :key="person.id" :value="person.id"
                :label="[person.name, person.department].filter(Boolean).join(' · ')" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <p v-if="testAccount">发票接收测试账号（{{ testAccount.username }}）也会收到开票需求。</p>
        <template v-else-if="canCreateTest">
          <el-form-item label="测试账号密码"><el-input v-model="form.password" type="password" show-password autocomplete="new-password" /></el-form-item>
          <el-button :disabled="form.password.length < 12" :loading="busy" @click="createTest">创建客户部测试账号</el-button>
        </template>
      </AppForm>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="close()">关闭</el-button>
      <el-button v-if="canEdit" type="primary" :loading="busy" :disabled="loading || !settings || !form.userIds.length" @click="save">保存接收人</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed, onMounted, reactive, ref} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'

const emit = defineEmits(['close'])
const settings = ref(), loading = ref(false), busy = ref(false), error = ref('')
const form = reactive({userIds:[], password:''})
const canCreateTest = hasPermission('system:users:write')
const canEdit = canCreateTest || hasPermission('finance:write') || hasPermission('projects:write')
const users = computed(() => settings.value?.users || [])
const testAccount = computed(() => users.value.find(person => person.username === 'invoice_receiver_test'))
const groups = computed(() => [
  {label:'客户部 / 销售部', users:users.value.filter(person => person.customer_department)},
  {label:'其他部门', users:users.value.filter(person => !person.customer_department)},
])
async function load() {
  loading.value = true
  try {
    settings.value = await api.get('/invoice-workflow/settings')
    form.userIds = settings.value.user_ids
  } catch (e) { error.value = getLocalizedErrorMessage(e, '读取财务设置失败') }
  finally { loading.value = false }
}
async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    settings.value = await api.put('/invoice-workflow/settings', {revision:settings.value.revision, user_ids:form.userIds})
    form.userIds = settings.value.user_ids
    ElMessage.success('开票接收人已保存')
  } catch (e) { error.value = getLocalizedErrorMessage(e, '保存财务设置失败') }
  finally { busy.value = false }
}
async function createTest() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await api.post('/invoice-workflow/settings/test-recipient', {password:form.password})
    form.password = ''
    const current = form.userIds
    await load()
    form.userIds = current
    ElMessage.success('发票接收测试账号已创建')
  } catch (e) { error.value = getLocalizedErrorMessage(e, '创建测试账号失败') }
  finally { busy.value = false }
}
function close(done) {
  if (busy.value) return
  if (typeof done === 'function') done()
  emit('close')
}
onMounted(load)
</script>
