<template>
  <div class="sub-client-orders">
    <AppForm data-auto-draft="off" :model="detailFilters" inline class="sub-client-order-filters" @submit.prevent="search">
      <el-form-item label="关键词">
        <el-input v-model="detailFilters.keyword" clearable maxlength="200"
          placeholder="订单号、项目名称、子客户" @input="queueSearch" />
      </el-form-item>
      <el-form-item v-if="client !== 'unlinked' && filters.presence !== 'without' && detailFilters.presence !== 'without'" label="子客户">
        <el-select v-model="detailFilters.subClientId" aria-label="筛选子客户" placeholder="全部子客户"
          filterable clearable :loading="loading && !subClientsLoaded" no-data-text="该客户未登记子客户" @change="search">
          <el-option v-for="child in subClients" :key="child.id" :value="child.id"
            :label="[child.client_short_name || child.client_name, child.sub_client_code].filter(Boolean).join(' · ')" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="filters.presence === 'all'">
        <el-radio-group v-model="detailFilters.presence" size="small" aria-label="项目的子客户关联状态" @change="changePresence">
          <el-radio-button value="all">全部项目</el-radio-button>
          <el-radio-button value="with">有子客户</el-radio-button>
          <el-radio-button value="without">无子客户</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item><el-button native-type="submit" size="small">查询</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="load">重试</el-button>
    </el-alert>
    <el-table v-loading="loading" :data="rows" row-key="id" border size="small" empty-text="没有符合条件的项目"
      :default-sort="{prop:'received_at', order:'descending'}" @sort-change="changeSort">
      <el-table-column type="index" label="序号" width="64" align="center" :index="orderIndex" />
      <el-table-column prop="order_no" label="订单号" min-width="145" sortable="custom" />
      <el-table-column prop="project_name" label="项目名称" min-width="190" show-overflow-tooltip sortable="custom" />
      <el-table-column prop="sub_client" label="子客户" min-width="155" show-overflow-tooltip sortable="custom">
        <template #default="{ row }">
          <span v-if="row.sub_client_id">{{ row.sub_client_short_name || row.sub_client_name || '已关联子客户' }}</span>
          <span v-else class="no-sub-client">未关联子客户</span>
        </template>
      </el-table-column>
      <el-table-column prop="received_at" label="接单／登记时间" min-width="175" sortable="custom">
        <template #default="{ row }">{{ formatBusinessDateTimeMinute(row.received_at) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="limit" :page-sizes="[15, 20, 50, 100]"
      :total="total" layout="total, sizes, prev, pager, next" @update:page-size="changePageSize" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getTranslationSubClientOrders } from '@/api/translationSubClientQuery'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({
  client: { type: String, required: true },
  filters: { type: Object, required: true },
})
const detailFilters = reactive({ keyword:'', subClientId:'', presence:'all' })
const sort = reactive({ by:'received_at', direction:'desc' })
const subClients = ref([])
const subClientsLoaded = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const limit = ref(15)
const orderIndex = index => (page.value - 1) * limit.value + index + 1
let controller
let sequence = 0
let timer

async function load() {
  clearTimeout(timer)
  controller?.abort()
  controller = new AbortController()
  const request = ++sequence
  loading.value = true
  error.value = ''
  rows.value = []
  try {
    const result = await getTranslationSubClientOrders({
      ...props.filters,
      client: props.client,
      presence: props.filters.presence === 'all' ? detailFilters.presence : props.filters.presence,
      project_keyword: detailFilters.keyword.trim(),
      sub_client_id: detailFilters.subClientId || undefined,
      sort_by: sort.by,
      sort_direction: sort.direction,
      skip: (page.value - 1) * limit.value,
      limit: limit.value,
    }, controller.signal)
    if (request !== sequence) return
    rows.value = result.items
    total.value = result.total
    subClients.value = result.sub_clients || []
    subClientsLoaded.value = Array.isArray(result.sub_clients)
  } catch (exception) {
    if (request === sequence && exception?.code !== 'ERR_CANCELED') {
      error.value = getLocalizedErrorMessage(exception, '加载客户项目失败')
    }
  } finally {
    if (request === sequence) loading.value = false
  }
}

function search() {
  clearTimeout(timer)
  if (page.value === 1) return load()
  page.value = 1
}

function queueSearch() {
  clearTimeout(timer)
  if (!detailFilters.keyword.trim()) return search()
  controller?.abort()
  sequence++
  timer = setTimeout(search, 400)
}

function changePresence() {
  if (detailFilters.presence === 'without') detailFilters.subClientId = ''
  return search()
}

function changeSort({ prop, order }) {
  const by = order ? prop : 'received_at'
  const direction = order === 'ascending' ? 'asc' : 'desc'
  if (sort.by === by && sort.direction === direction) return
  Object.assign(sort, { by, direction })
  return search()
}

function changePageSize(size) {
  page.value = 1
  limit.value = size
}

watch([page, limit], load)
onMounted(load)
onBeforeUnmount(() => { clearTimeout(timer); sequence++; controller?.abort() })
</script>

<style scoped>
.sub-client-orders { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; padding: 12px 20px; }
.sub-client-order-filters { display:flex; flex-wrap:wrap; gap:8px 12px; }
.sub-client-order-filters :deep(.el-form-item) { margin:0; }
.sub-client-order-filters :deep(.el-input), .sub-client-order-filters :deep(.el-select) { width:180px; max-width:100%; }
.sub-client-orders :deep(.el-pagination) { flex-wrap: wrap; }
.no-sub-client { color: var(--el-text-color-secondary); }
</style>
