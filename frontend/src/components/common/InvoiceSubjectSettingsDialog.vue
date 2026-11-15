<template>
  <DraggableFormDialog
    :model-value="true"
    title="发票设置"
    width="min(720px, calc(100vw - 32px))"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="$emit('close')"
  >
    <div v-loading="loading" class="invoice-subjects">
      <h4>开票主体</h4>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-button v-if="error" @click="load">重新加载</el-button>
      <InvoiceSubjectEditor
        v-for="subject in subjects"
        :key="subject.key"
        :subject="subject"
        :can-write="canWrite"
      />
    </div>
    <template #footer><el-button @click="$emit('close')">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed, onBeforeUnmount, onMounted, ref} from 'vue'
import {connectInvoiceParties, getInvoiceSubjects, invoicePartiesEvent} from '@/api/invoiceParties'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {hasPermission} from '@/utils/permission'
import DraggableFormDialog from './DraggableFormDialog.vue'
import InvoiceSubjectEditor from './InvoiceSubjectEditor.vue'

defineEmits(['close'])
const canWrite = computed(() => hasPermission(['system:users:write', 'system:organization:write']))
const subjects = ref([])
const loading = ref(false)
const error = ref('')
let request = 0

async function load() {
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const result = await getInvoiceSubjects()
    if (current === request) subjects.value = result.items || []
  } catch (e) {
    if (current === request) error.value = getLocalizedErrorMessage(e, '主体开票信息加载失败')
  } finally {
    if (current === request) loading.value = false
  }
}

function refreshSubjects(event) {
  if (event.detail?.kind === 'subject') void load()
}

onMounted(() => {
  connectInvoiceParties()
  window.addEventListener(invoicePartiesEvent, refreshSubjects)
  void load()
})
onBeforeUnmount(() => {
  request++
  window.removeEventListener(invoicePartiesEvent, refreshSubjects)
})
</script>

<style scoped>
.invoice-subjects{display:grid;gap:12px}
.invoice-subjects h4{margin:0}
</style>
