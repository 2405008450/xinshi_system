<template>
  <section class="document-section-attachments company-attachments" v-loading="loading">
    <div class="company-attachments__heading">
      <h4>{{ title }} <span>({{ attachments.length }}/50)</span></h4>
      <el-button v-if="canEdit" type="primary" plain :disabled="loading || !!loadError || attachments.length >= 50" @click="inputRef.click()">上传附件</el-button>
      <input ref="inputRef" type="file" multiple :accept="extensions.join(',')" class="company-attachments__input" @change="selectFiles" />
    </div>
    <p v-if="canEdit" class="company-attachments__hint">支持办公文档、PDF、TXT、CSV、常见图片及 ZIP/RAR/7Z；单个文件不超过20MB，每{{ entityLabel }}最多50个。</p>
    <el-alert v-if="loadError" :title="loadError" type="warning" :closable="false" show-icon />
    <el-button v-if="loadError" link type="primary" :disabled="loading" @click="load">重新加载</el-button>
    <div v-for="item in queue" :key="item.id" class="company-attachments__upload">
      <span class="company-attachments__name">{{ item.file.name }}</span>
      <el-progress v-if="item.status === 'uploading'" :percentage="item.progress" :stroke-width="6" />
      <span v-else :class="{ 'company-attachments__error': item.status === 'failed' }">{{ item.message }}</span>
      <el-button v-if="canEdit && item.status === 'failed'" link type="primary" :disabled="uploading" @click="retry(item)">重试</el-button>
      <el-button v-if="item.status !== 'uploading'" link @click="queue = queue.filter(row => row.id !== item.id)">移除</el-button>
    </div>
    <el-table v-if="attachments.length" :data="attachments" size="small">
      <el-table-column prop="originalName" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column label="大小" width="100"><template #default="{ row }">{{ formatSize(row.fileSize) }}</template></el-table-column>
      <el-table-column label="上传人" width="110"><template #default="{ row }">{{ row.uploadedByName || '-' }}</template></el-table-column>
      <el-table-column label="上传时间" min-width="165"><template #default="{ row }">{{ formatTime(row.uploadedAt) }}</template></el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :loading="downloading.has(row.id)" @click="download(row)">下载</el-button>
          <el-button v-if="canEdit" link type="danger" :loading="deleting.has(row.id)" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else-if="!loading && !loadError" description="暂无附件" :image-size="64" />
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({
  sectionId: { type: String, required: true },
  adapter: { type: Object, required: true },
  canEdit: { type: Boolean, default: false },
  title: { type: String, default: '栏目附件' },
  entityLabel: { type: String, default: '栏目' }
})
const emit = defineEmits(['changed'])
const extensions = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.csv', '.jpg', '.jpeg', '.png', '.webp', '.zip', '.rar', '.7z']
const attachments = ref([])
const queue = ref([])
const loading = ref(false)
const loadError = ref('')
const uploading = ref(false)
const inputRef = ref(null)
const downloading = ref(new Set())
const deleting = ref(new Set())
const controller = new AbortController()
let disposed = false
let nextId = 0

const formatSize = bytes => bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`
const formatTime = formatBusinessDateTime

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const result = await props.adapter.list(props.sectionId, controller.signal)
    if (!disposed) { attachments.value = result; emit('changed', result) }
  } catch (error) {
    if (!disposed) loadError.value = error?.response?.status === 503 ? `${props.title}尚未启用` : getLocalizedErrorMessage(error, '附件加载失败')
  } finally {
    loading.value = false
  }
}

function validationError(file) {
  if (!file.size) return '不能上传空文件'
  if (file.size > 20 * 1024 * 1024) return '单个附件不能超过20MB'
  if (!extensions.includes('.' + file.name.split('.').pop().toLowerCase())) return '不支持的附件格式'
  return ''
}

function selectFiles(event) {
  if (!props.canEdit || disposed || loadError.value) return
  for (const file of Array.from(event.target.files || [])) {
    const message = validationError(file)
    queue.value.push({ id: ++nextId, file, progress: 0, status: message ? 'failed' : 'pending', message: message || '等待上传' })
  }
  event.target.value = ''
  processQueue()
}

async function retry(item) {
  if (!props.canEdit || disposed || loadError.value) return
  const message = validationError(item.file)
  if (message) return ElMessage.warning(message)
  item.status = 'pending'
  item.message = '等待上传'
  await processQueue()
}

async function processQueue() {
  if (uploading.value || !props.canEdit || disposed || loadError.value) return
  uploading.value = true
  try {
    while (!disposed) {
      const item = queue.value.find(row => row.status === 'pending')
      if (!item) break
      if (attachments.value.length >= 50) {
        item.status = 'failed'
        item.message = `每个${props.entityLabel}最多上传50个附件`
        continue
      }
      item.status = 'uploading'
      item.progress = 0
      try {
        const saved = await props.adapter.upload(props.sectionId, item.file, event => {
          item.progress = Math.min(99, Math.round(event.loaded / (event.total || item.file.size) * 100))
        }, controller.signal)
        if (disposed) break
        item.status = 'success'
        item.message = '上传成功'
        item.progress = 100
        attachments.value = [saved, ...attachments.value]
        emit('changed', attachments.value)
      } catch (error) {
        if (disposed) break
        item.status = 'failed'
        item.message = getLocalizedErrorMessage(error, '附件上传失败')
      }
    }
  } finally {
    uploading.value = false
  }
}

async function download(row) {
  if (disposed || downloading.value.has(row.id)) return
  downloading.value.add(row.id)
  try {
    const blob = await props.adapter.download(props.sectionId, row.id, controller.signal)
    if (disposed) return
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.originalName
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) {
    if (!disposed) ElMessage.error(getLocalizedErrorMessage(error, '附件下载失败'))
  } finally {
    downloading.value.delete(row.id)
  }
}

async function remove(row) {
  if (!props.canEdit || disposed || deleting.value.has(row.id)) return
  try {
    await ElMessageBox.confirm(`确定删除附件“${row.originalName}”吗？删除后不可恢复。`, '删除附件', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  if (disposed || !props.canEdit) return
  deleting.value.add(row.id)
  try {
    await props.adapter.remove(props.sectionId, row.id, controller.signal)
    if (disposed) return
    attachments.value = attachments.value.filter(item => item.id !== row.id)
    emit('changed', attachments.value)
    ElMessage.success('附件已删除')
  } catch (error) {
    if (!disposed) ElMessage.error(getLocalizedErrorMessage(error, '附件删除失败'))
  } finally {
    deleting.value.delete(row.id)
  }
}

onMounted(load)
onBeforeUnmount(() => { disposed = true; controller.abort() })
defineExpose({
  isBusy: computed(() => uploading.value || deleting.value.size > 0),
  hasPendingFiles: computed(() => queue.value.some(item => ['pending', 'failed'].includes(item.status)))
})
</script>

<style scoped>
.company-attachments{margin-top:24px;border-top:1px solid var(--el-border-color-lighter);padding-top:16px}
.company-attachments__heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.company-attachments__heading h4{margin:0;font-size:16px}
.company-attachments__heading span,.company-attachments__hint{color:var(--el-text-color-secondary);font-size:12px}
.company-attachments__input{display:none}
.company-attachments__upload{display:flex;align-items:center;gap:12px;margin:10px 0;flex-wrap:wrap;font-size:13px}
.company-attachments__name{overflow-wrap:anywhere;max-width:50%}
.company-attachments__upload .el-progress{width:160px}
.company-attachments__error{color:var(--el-color-danger)}
</style>
