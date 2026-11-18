<template>
  <DraggableFormDialog :model-value="true" title="子客户查询"
    width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body
    class="sub-client-query-dialog" @update:model-value="closeIfHidden">
    <AppForm data-auto-draft="off" :model="filters" inline @submit.prevent="search">
      <el-form-item label="客户或子客户">
        <el-input v-model="filters.keyword" clearable maxlength="200"
          placeholder="输入名称、简称或编号" @input="queueSearch" />
      </el-form-item>
      <el-form-item><el-button type="primary" native-type="submit">查询</el-button></el-form-item>
    </AppForm>
    <el-alert v-if="error" type="error" :title="error" :closable="false">
      <el-button link @click="load">重试</el-button>
    </el-alert>
    <el-table v-loading="loading" :data="rows" row-key="id" border
      empty-text="没有符合条件的客户">
      <el-table-column type="expand" width="48">
        <template #default="{ row }">
          <div class="sub-client-query-children">
            <el-table :data="row.sub_clients" row-key="id" size="small" border>
              <el-table-column prop="sub_client_code" label="子客户编号" min-width="150" />
              <el-table-column prop="client_name" label="子客户全称" min-width="160" />
              <el-table-column prop="client_short_name" label="子客户简称" min-width="120" />
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="client_code" label="客户编号" min-width="150" />
      <el-table-column prop="client_name" label="客户全称" min-width="160" />
      <el-table-column prop="client_short_name" label="客户简称" min-width="120" />
      <el-table-column label="子客户数" width="94" align="center">
        <template #default="{ row }">{{ row.sub_clients.length }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <div class="sub-client-query-footer">
        <el-pagination v-model:current-page="page" v-model:page-size="limit"
          :total="total" :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next"
          @change="changePage" />
        <el-button @click="emit('close')">关闭</el-button>
      </div>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getClientPage } from '@/api/clients'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const emit = defineEmits(['close'])
const props = defineProps({ initialKeyword: { type: String, default: '' } })
const filters = reactive({ keyword: props.initialKeyword })
const page = ref(1)
const limit = ref(10)
const total = ref(0)
const rows = ref([])
const loading = ref(false)
const error = ref('')
let timer
let controller
let sequence = 0
let appliedKeyword = filters.keyword.trim()

async function load() {
  controller?.abort()
  controller = new AbortController()
  const request = ++sequence
  loading.value = true
  error.value = ''
  try {
    const result = await getClientPage({
      has_sub_clients: true,
      sub_client_query: appliedKeyword || undefined,
      skip: (page.value - 1) * limit.value,
      limit: limit.value,
    }, { signal: controller.signal })
    if (request !== sequence) return
    rows.value = result.items
    total.value = result.total
  } catch (e) {
    if (request === sequence && e?.code !== 'ERR_CANCELED') {
      error.value = getLocalizedErrorMessage(e, '查询子客户失败，请重试')
    }
  } finally {
    if (request === sequence) loading.value = false
  }
}

function search() {
  clearTimeout(timer)
  appliedKeyword = filters.keyword.trim()
  page.value = 1
  return load()
}

function queueSearch() {
  clearTimeout(timer)
  if (!filters.keyword.trim()) return search()
  timer = setTimeout(search, 400)
}

function changePage() {
  if (filters.keyword.trim() !== appliedKeyword) return search()
  return load()
}

function closeIfHidden(value) {
  if (!value) emit('close')
}

onMounted(load)
onBeforeUnmount(() => { clearTimeout(timer); sequence++; controller?.abort() })
</script>

<style scoped>
.sub-client-query-children { padding: 12px 24px; }
.sub-client-query-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
:global(.sub-client-query-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.sub-client-query-dialog > .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.sub-client-query-dialog > .el-dialog__footer) { flex-shrink: 0; border-top: 1px solid var(--el-border-color-lighter); }
</style>
