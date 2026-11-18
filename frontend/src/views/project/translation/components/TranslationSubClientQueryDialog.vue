<template>
  <DraggableFormDialog :model-value="true" title="子客户查询" class="translation-sub-client-query"
    width="min(1120px, calc(100vw - 32px))" top="5vh" append-to-body @update:model-value="closeIfHidden">
    <AppForm data-auto-draft="off" :model="filters" inline @submit.prevent="search">
      <el-form-item label="月份">
        <el-date-picker v-model="filters.months" type="months" value-format="YYYY-MM" format="YYYY-MM"
          placeholder="选择一个或多个月份" :clearable="false" :show-confirm="true" :show-footer="true" @change="search" />
      </el-form-item>
      <el-form-item label="客户">
        <el-input v-model="filters.keyword" clearable maxlength="200" placeholder="客户全称、简称或编号" @input="queueSearch" />
      </el-form-item>
      <el-form-item label="子客户">
        <el-select v-model="filters.presence" aria-label="子客户关联状态" style="width: 120px" @change="search">
          <el-option label="全部项目" value="all" />
          <el-option label="有子客户" value="with" />
          <el-option label="无子客户" value="without" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button native-type="submit" type="primary">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
      <el-form-item v-if="canOpenDirectory">
        <el-button @click="$emit('open-directory', filters.keyword.trim())">打开客户管理 · 子客户</el-button>
      </el-form-item>
    </AppForm>
    <p class="month-hint">按客户接单月份查询，未填写接单时间的项目按登记月份归入。展开客户可查看项目。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false">
      <el-button link @click="search">重试</el-button>
    </el-alert>
    <el-table v-loading="loading" :data="rows" row-key="key" :expand-row-keys="expanded"
      border @expand-change="onExpandChange" empty-text="没有符合条件的客户项目">
      <el-table-column type="expand" width="46">
        <template #default="{ row }">
          <TranslationSubClientOrders v-if="expanded.includes(row.key)" :client="row.key" :filters="applied" />
        </template>
      </el-table-column>
      <el-table-column label="客户简称" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.client_short_name || row.client_name || '未关联客户' }}</template>
      </el-table-column>
      <el-table-column prop="client_name" label="客户全称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="order_count" label="项目数" width="95" align="center" />
      <el-table-column prop="with_sub_client" label="有子客户" width="100" align="center" />
      <el-table-column prop="without_sub_client" label="无子客户" width="100" align="center" />
    </el-table>
    <template #footer>
      <div class="sub-client-query-footer">
        <el-pagination v-model:current-page="page" v-model:page-size="limit" :total="total"
          :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next" @change="changePage" />
        <el-button @click="$emit('close')">关闭</el-button>
      </div>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getTranslationSubClientCustomers } from '@/api/translationSubClientQuery'
import { businessDateTimeInputValue } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import TranslationSubClientOrders from './TranslationSubClientOrders.vue'

defineProps({ canOpenDirectory: Boolean })
const emit = defineEmits(['close', 'open-directory'])
const currentMonth = () => businessDateTimeInputValue().slice(0, 7)
const filters = reactive({ months: [currentMonth()], keyword: '', presence: 'all' })
const applied = ref({ months: filters.months.join(','), keyword: '', presence: filters.presence })
const rows = ref([])
const expanded = ref([])
const page = ref(1)
const limit = ref(20)
const total = ref(0)
const loading = ref(false)
const error = ref('')
let controller
let sequence = 0
let timer

async function load() {
  controller?.abort()
  controller = new AbortController()
  const request = ++sequence
  loading.value = true
  error.value = ''
  expanded.value = []
  rows.value = []
  try {
    const result = await getTranslationSubClientCustomers({
      ...applied.value, skip: (page.value - 1) * limit.value, limit: limit.value,
    }, controller.signal)
    if (request !== sequence) return
    rows.value = result.items.map(row => ({ ...row, key: row.client_id || 'unlinked' }))
    total.value = result.total
  } catch (exception) {
    if (request === sequence && exception?.code !== 'ERR_CANCELED') {
      error.value = getLocalizedErrorMessage(exception, '查询客户项目失败')
    }
  } finally {
    if (request === sequence) loading.value = false
  }
}

function search() {
  clearTimeout(timer)
  if (!filters.months?.length) filters.months = [currentMonth()]
  applied.value = { months: filters.months.join(','), keyword: filters.keyword.trim(), presence: filters.presence }
  page.value = 1
  total.value = 0
  return load()
}

function queueSearch() {
  clearTimeout(timer)
  if (!filters.keyword.trim()) return search()
  timer = setTimeout(search, 400)
}

function changePage() {
  return filters.keyword.trim() !== applied.value.keyword ? search() : load()
}

function reset() {
  filters.months = [currentMonth()]
  filters.keyword = ''
  filters.presence = 'all'
  return search()
}

function onExpandChange(_row, expandedRows) {
  expanded.value = expandedRows.map(row => row.key)
}

function closeIfHidden(visible) {
  if (!visible) emit('close')
}

onMounted(load)
onBeforeUnmount(() => { clearTimeout(timer); sequence++; controller?.abort() })
</script>

<style scoped>
.month-hint { color: var(--el-text-color-secondary); font-size: 13px; margin: 0 0 12px; }
.sub-client-query-footer { display: flex; align-items: center; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
:global(.translation-sub-client-query) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.translation-sub-client-query > .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.translation-sub-client-query > .el-dialog__footer) { flex-shrink: 0; border-top: 1px solid var(--el-border-color-lighter); }
</style>
