<template>
  <section class="field-work">
    <div class="field-work-toolbar">
      <el-input v-model="keyword" :placeholder="customerView ? '搜索客户、外勤人、地点或说明' : '搜索客户、地点或说明'"
        aria-label="搜索外勤记录" clearable maxlength="200" @keyup.enter="search" />
      <el-button @click="search">查询</el-button>
      <el-button v-if="!customerView" type="primary" @click="openEditor()">新增外勤</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="rows" border empty-text="暂无外勤记录">
      <el-table-column v-if="customerView" prop="owner_name" label="外勤人" min-width="100" />
      <el-table-column prop="type_label" label="外勤类型" min-width="160" show-overflow-tooltip />
      <el-table-column label="外勤时间" min-width="185">
        <template #default="{ row }">{{ formatBusinessDateTimeMinute(row.start_at) }}<br>至 {{ formatBusinessDateTimeMinute(row.end_at) }}</template>
      </el-table-column>
      <el-table-column prop="location" label="地点" min-width="130" show-overflow-tooltip />
      <el-table-column prop="client_name" label="客户名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="companion_names" label="陪同人" min-width="100" show-overflow-tooltip />
      <el-table-column prop="notes" label="补充说明" min-width="130" show-overflow-tooltip />
      <el-table-column label="打卡照片" width="105">
        <template #default="{ row }">
          <el-button v-if="row.has_photo" link type="primary" @click="showPhoto(row)">查看照片</el-button>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column v-if="!customerView" label="操作" :width="canReport ? 185 : 76" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEditor(row)">编辑</el-button>
          <el-button v-if="canReport" link type="primary" @click="openReport(row)">增至工作报告</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next"
      @current-change="load" />

    <FieldWorkEditor v-if="editorOpen" :record="editing" @close="editorOpen = false" @saved="onSaved" />
    <DraggableFormDialog v-model="photoOpen" title="外勤打卡照片" width="min(760px, calc(100vw - 32px))" @close="clearPhoto">
      <div v-loading="photoLoading" class="field-work-photo">
        <img v-if="photoUrl" :src="photoUrl" alt="外勤打卡照片">
        <el-alert v-if="photoError" :title="photoError" type="error" :closable="false" />
      </div>
    </DraggableFormDialog>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getFieldWork, getFieldWorkPhoto } from '@/api/fieldWork'
import { formatBusinessDateTimeMinute } from '@/utils/dateTime'
import { hasPermission } from '@/utils/permission'
import FieldWorkEditor from './FieldWorkEditor.vue'

const props = defineProps({ customerView: Boolean })
const canReport = hasPermission('reports:read')
const keyword = ref('')
const page = ref(1)
const total = ref(0)
const rows = ref([])
const loading = ref(false)
const error = ref('')
const editorOpen = ref(false)
const editing = ref(null)
let searchTimer, listController, photoController
let appliedKeyword = ''

async function load() {
  listController?.abort()
  const controller = new AbortController()
  listController = controller
  loading.value = true
  error.value = ''
  try {
    const data = await getFieldWork(props.customerView, { keyword: appliedKeyword, page: page.value }, controller.signal)
    if (controller.signal.aborted) return
    total.value = data.total
    rows.value = data.items.map(row => ({
      ...row, companion_names: row.companions.map(person => person.name).join('、'),
    }))
  } catch (reason) {
    if (!controller.signal.aborted) error.value = reason.detail || '读取外勤记录失败'
  } finally {
    if (listController === controller) loading.value = false
  }
}

function search() {
  clearTimeout(searchTimer)
  appliedKeyword = keyword.value.trim()
  page.value = 1
  return load()
}

watch(keyword, value => {
  clearTimeout(searchTimer)
  if (!value.trim()) search()
  else searchTimer = setTimeout(search, 400)
})

function openEditor(record = null) {
  editing.value = record
  editorOpen.value = true
}

function onSaved() {
  editorOpen.value = false
  ElMessage.success('外勤记录已保存')
  search()
}

function openReport(row) {
  window.dispatchEvent(new CustomEvent('edit-field-work-report', { detail: row }))
}

const photoOpen = ref(false)
const photoUrl = ref('')
const photoLoading = ref(false)
const photoError = ref('')

function clearPhoto() {
  photoController?.abort()
  if (photoUrl.value) URL.revokeObjectURL(photoUrl.value)
  photoUrl.value = ''
  photoError.value = ''
}

async function showPhoto(row) {
  clearPhoto()
  const controller = new AbortController()
  photoController = controller
  photoOpen.value = true
  photoLoading.value = true
  try {
    const blob = await getFieldWorkPhoto(row.id, props.customerView, controller.signal)
    if (!controller.signal.aborted) photoUrl.value = URL.createObjectURL(blob)
  } catch {
    if (!controller.signal.aborted) photoError.value = '读取外勤照片失败'
  } finally {
    if (photoController === controller) photoLoading.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  listController?.abort()
  clearPhoto()
})
</script>

<style scoped>
.field-work { display: grid; gap: 12px; min-width: 0; }
.field-work-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.field-work-toolbar .el-input { width: min(320px, 100%); }
.field-work-toolbar .el-button { margin-left: 0; }
.field-work-photo { min-height: 80px; text-align: center; }
.field-work-photo img { max-width: 100%; max-height: 68vh; object-fit: contain; }
</style>
