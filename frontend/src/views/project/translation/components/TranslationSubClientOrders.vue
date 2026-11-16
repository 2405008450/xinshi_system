<template>
  <div class="sub-client-orders">
    <el-radio-group v-model="presence" size="small" aria-label="子客户关联状态" @change="search">
      <el-radio-button value="all">全部项目</el-radio-button>
      <el-radio-button value="with">有子客户</el-radio-button>
      <el-radio-button value="without">无子客户</el-radio-button>
    </el-radio-group>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="load">重试</el-button>
    </el-alert>
    <el-table v-loading="loading" :data="rows" row-key="id" border size="small" empty-text="没有符合条件的项目">
      <el-table-column prop="order_no" label="订单号" min-width="145" />
      <el-table-column prop="project_name" label="项目名称" min-width="190" show-overflow-tooltip />
      <el-table-column label="子客户" min-width="155" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.sub_client_id">{{ row.sub_client_short_name || row.sub_client_name || '已关联子客户' }}</span>
          <span v-else class="no-sub-client">未关联子客户</span>
        </template>
      </el-table-column>
      <el-table-column label="接单／登记时间" min-width="175">
        <template #default="{ row }">{{ formatBusinessDateTimeMinute(row.received_at) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="total > limit" v-model:current-page="page" :page-size="limit"
      :total="total" layout="total, prev, pager, next" @current-change="load" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getTranslationSubClientOrders } from '@/api/translationSubClientQuery'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({
  client: { type: String, required: true },
  filters: { type: Object, required: true },
})
const presence = ref('all')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const limit = 15
let controller
let sequence = 0

async function load() {
  controller?.abort()
  controller = new AbortController()
  const request = ++sequence
  loading.value = true
  error.value = ''
  rows.value = []
  try {
    const result = await getTranslationSubClientOrders({
      ...props.filters, client: props.client, presence: presence.value, skip: (page.value - 1) * limit, limit,
    }, controller.signal)
    if (request !== sequence) return
    rows.value = result.items
    total.value = result.total
  } catch (exception) {
    if (request === sequence && exception?.code !== 'ERR_CANCELED') {
      error.value = getLocalizedErrorMessage(exception, '加载客户项目失败')
    }
  } finally {
    if (request === sequence) loading.value = false
  }
}

function search() {
  page.value = 1
  total.value = 0
  void load()
}

onMounted(load)
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>

<style scoped>
.sub-client-orders { display: grid; gap: 10px; padding: 12px 20px; }
.no-sub-client { color: var(--el-text-color-secondary); }
</style>
