<template>
  <ClientEditor v-if="editorTarget" :key="editorTarget.subClientId || editorTarget.clientId"
    :editor-client-id="editorTarget.clientId" :editor-sub-client-id="editorTarget.subClientId"
    @editor-closed="close" @editor-load-error="editorTarget = null" />
  <DraggableFormDialog v-else :model-value="true" title="客户管理" width="min(720px, calc(100vw - 32px))" top="8vh" @update:model-value="close">
    <div v-loading="loading" class="client-window-content">
      <el-alert v-if="error" :title="error" type="error" :closable="false">
        <el-button link @click="load(request)">重试</el-button>
      </el-alert>
      <template v-else-if="matches.length">
        <p>请选择对应的客户</p>
        <el-button v-for="item in matches" :key="item.sub_client_id || item.client_id" link type="primary" @click="select(item)">
          {{ item.name || item.short_name }}（{{ item.code }}）
        </el-button>
      </template>
      <template v-else-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="客户简称" client-link-disabled>{{ detail.short_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户编号">{{ detail.code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户全称" :span="2">{{ detail.name || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.parent" label="所属客户" :span="2">
            <el-button link type="primary" @click="select(detail.parent)">{{ detail.parent.short_name || detail.parent.name }}</el-button>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.children.length" label="子客户" :span="2">
            <el-button v-for="child in detail.children" :key="child.sub_client_id" link type="primary" @click="select(child)">{{ child.short_name || child.name }}</el-button>
          </el-descriptions-item>
        </el-descriptions>
        <el-table v-if="detail.contacts.length" :data="detail.contacts" border size="small" class="client-window-contacts">
          <el-table-column prop="name" label="联系人" min-width="120" />
          <el-table-column prop="method" label="联系方式" min-width="180" />
          <el-table-column v-if="detail.full_access" prop="description" label="说明" min-width="160" />
        </el-table>
        <el-empty v-else description="暂无联系人" :image-size="48" />
      </template>
    </div>
    <template #footer>
      <el-button v-if="detail?.can_manage && canWrite" type="primary" @click="openEditor">进入客户管理</el-button>
      <el-button v-else-if="detail?.can_manage" tag="a" :href="managementUrl" target="_blank" rel="noopener" type="primary">查看客户列表</el-button>
      <el-button @click="close">关闭</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { clientManagementTarget } from '@/utils/clientManagementWindow'
import { hasPermission } from '@/utils/permission'

const ClientEditor = defineAsyncComponent(() => import('@/views/client/Clients.vue'))
const router = useRouter()
const canWrite = computed(() => hasPermission('clients:write'))
const editorTarget = ref(null)
const loading = ref(false)
const detail = ref(null)
const matches = ref([])
const error = ref('')
const request = ref(null)
let controller
const managementUrl = computed(() => router.resolve({
  name: 'Clients',
  query: { client_id: detail.value?.client_id, sub_client_id: detail.value?.sub_client_id || undefined },
}).href)

async function load(params) {
  controller?.abort()
  const active = new AbortController()
  controller = active
  request.value = params
  loading.value = true
  detail.value = null
  matches.value = []
  error.value = ''
  try {
    const result = await api.get('/client-management-window', { params, signal: active.signal })
    if (active.signal.aborted) return
    if (result.matches) matches.value = result.matches
    else detail.value = result
  } catch (reason) {
    if (!active.signal.aborted) error.value = reason?.message || '读取客户失败'
  } finally {
    if (!active.signal.aborted) loading.value = false
  }
}

function select(item) {
  load({ client_id: item.client_id, sub_client_id: item.sub_client_id })
}
function openEditor() {
  editorTarget.value = {
    clientId: detail.value.client_id,
    subClientId: detail.value.sub_client_id || undefined,
  }
}
function close() {
  clientManagementTarget.value = null
}
watch(clientManagementTarget, target => {
  if (!target) return
  editorTarget.value = null
  load(target)
}, { immediate: true })
window.addEventListener('auth-session-clearing', close)
onBeforeUnmount(() => {
  controller?.abort()
  window.removeEventListener('auth-session-clearing', close)
})
</script>

<style scoped>
.client-window-content { min-height: 88px; max-height: 65vh; overflow: auto; }
.client-window-contacts { margin-top: 12px; }
.client-window-content > .el-button { display: flex; margin: 6px 0; }
</style>
