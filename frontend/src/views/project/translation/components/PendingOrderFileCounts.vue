<template>
  <section class="pending-file-counts">
    <div class="count-actions">
      <strong>工作量提取</strong>
      <span v-if="busy">已处理 {{ processed }} / {{ targets.length }} 个文件</span>
      <span v-else-if="results.length">已完成，成功 {{ successful.length - partialCount }} 个<span v-if="partialCount">，部分成功 {{ partialCount }} 个</span>，无法统计 {{ results.length - successful.length }} 个</span>
      <span v-else>等待取得文件</span>
      <el-button v-if="!busy && error && canStart" link type="primary" @click="start">重新统计</el-button>
    </div>
    <div v-if="plan.sourceKind === 'local' && !sources.size" class="count-actions">
      <el-button @click="folderInput.click()">选择同一文件夹继续统计</el-button>
      <input ref="folderInput" type="file" webkitdirectory multiple hidden @change="selectFolder" />
      <span>当前桌面客户端未提供文件读取权限。</span>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-progress v-if="busy || results.length" :percentage="Math.min(100, Math.round(processed / Math.max(1, targets.length) * 100))" />
    <template v-if="results.length">
      <el-table :data="results" row-key="id" border max-height="260" size="small">
        <el-table-column prop="orderNo" label="子订单号" min-width="165" />
        <el-table-column prop="path" label="相对路径" min-width="220" show-overflow-tooltip />
        <el-table-column v-for="metric in metrics" :key="metric.key" :label="metric.label" :min-width="metric.width">
          <template #default="{ row }">{{ row.values?.[metric.key]?.toLocaleString('zh-CN') ?? '—' }}</template>
        </el-table-column>
        <el-table-column prop="message" label="状态／说明" min-width="175" />
      </el-table>
      <small>应用后，已取得的统计结果带入对应子订单的我司统计。无法自动统计的项目可手动补填。</small>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import api from '@/api'
import { documentCountMetrics as metrics, documentCountValues, uploadDocumentCount, waitForDocumentCount } from '@/api/documentWordCounts'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { selectedFolderName } from '@/utils/translationFolderPaths'
import { countFileBatches, countPathKey, orderFileTargets } from '@/utils/translationFileCounts'

const props = defineProps({
  plan: { type: Object, required: true },
  rows: { type: Array, required: true },
  localFolderFiles: Map,
  uncListing: Promise,
})
const emit = defineEmits(['state'])
const folderInput = ref(null)
const sources = shallowRef(localSources(props.localFolderFiles || []))
const results = ref([])
const error = ref('')
const busy = ref(false)
const processed = ref(0)
let controller
const targets = computed(() => orderFileTargets(props.rows, props.plan.rootPath))
const canStart = computed(() => targets.value.length > 0 && (props.plan.sourceKind === 'unc' || sources.value.size > 0))
const successful = computed(() => results.value.filter(row => row.values))
const partialCount = computed(() => successful.value.filter(row => row.status === 'partial').length)

function localSources(files) {
  return new Map(Array.from(files, ([path, file]) => [countPathKey(path.slice(path.indexOf('/') + 1)), file]))
}

function selectFolder(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  results.value = []
  const folder = files[0].webkitRelativePath.split('/')[0]
  if (countPathKey(folder) !== countPathKey(selectedFolderName(props.plan.entries))) {
    error.value = '所选文件夹名称与订单根文件夹不一致，请重新选择。'
    return
  }
  sources.value = localSources(files.map(file => [file.webkitRelativePath, file]))
  error.value = ''
}

watch(canStart, ready => { if (ready) start() }, { immediate: true })
onBeforeUnmount(() => controller?.abort())

async function countBatch(batch, unc, signal, done) {
  const options = { include_hidden: false, include_extra: false }
  const config = { signal, timeout: 120000 }
  let request
  if (unc) {
    request = api.post('/document-word-count/paths', {
      path: props.plan.rootPath, relative_paths: batch.map(item => item.sourcePath), ...options,
    }, config)
  } else {
    request = uploadDocumentCount(batch.map(item => item.file), signal)
  }
  const { job_id: id } = await request
  return waitForDocumentCount(id, signal, job => {
    processed.value = done + (job.completed ?? job.files?.length ?? 0)
  })
}

async function start() {
  if (busy.value || !canStart.value) return
  controller = new AbortController()
  const { signal } = controller
  const unc = props.plan.sourceKind === 'unc'
  const currentTargets = targets.value
  const output = new Map()
  const ready = []
  const fail = ({ id, orderNo, path, fullPath }, message) => {
    output.set(id, { id, orderNo, path, fullPath, status: 'failed', message })
  }
  results.value = []
  error.value = ''
  processed.value = 0
  busy.value = true
  emit('state', { busy: true, items: [] })
  try {
    let listing = []
    if (unc) {
      const response = await props.uncListing || await api.post('/document-word-count/discover', {
        path: props.plan.rootPath, recursive: true,
      }, { signal, timeout: 60000 })
      listing = response.files
    }
    const shared = new Map(listing.map(file => [countPathKey(file.relative_path), file]))
    for (const item of currentTargets) {
      if (signal.aborted) return
      if (!/\.(docx?|xlsx?|pptx?|pdf|txt)$/i.test(item.path)) {
        fail(item, '该格式暂不支持自动统计')
        continue
      }
      const key = countPathKey(item.path)
      const source = unc ? shared.get(key) : sources.value.get(key)
      if (!source) {
        fail(item, '未找到与订单路径对应的文件')
        continue
      }
      try {
        const file = source.getSize ? null : source.getFile ? await source.getFile() : source
        const size = file?.size ?? await source.getSize()
        if (size > 50 * 1024 ** 2) {
          fail(item, '单文件超过 50 MB')
          continue
        }
        ready.push({ ...item, file, getFile: file ? null : source.getFile, sourcePath: source.relative_path, size })
      } catch {
        fail(item, '无法读取文件，请重新选择')
      }
    }
    processed.value = output.size
    for (const batch of countFileBatches(ready)) {
      if (signal.aborted) return
      const inputs = []
      for (const item of batch) {
        if (signal.aborted) return
        try {
          inputs.push(item.getFile ? { ...item, file: await item.getFile() } : item)
        } catch {
          fail(item, '无法读取文件正文')
        }
      }
      if (!inputs.length) { processed.value = output.size; continue }
      try {
        const files = await countBatch(inputs, unc, signal, output.size)
        const counts = new Map(files.map(file => [unc ? countPathKey(file.name) : file.file_index, file]))
        inputs.forEach((item, index) => {
          const statistics = counts.get(unc ? countPathKey(item.sourcePath) : index)
          const values = documentCountValues(statistics)
          const available = Object.keys(values).length
          if (available) {
            const { id, orderNo, path, fullPath } = item
            const complete = available === metrics.length
            output.set(id, { id, orderNo, path, fullPath, values,
              status: complete ? 'counted' : 'partial', message: complete ? '完成' : '部分口径无法统计' })
          } else {
            fail(item, statistics?.message || '没有收到有效统计结果')
          }
        })
      } catch (exception) {
        if (signal.aborted) return
        const message = getLocalizedErrorMessage(exception, '统计失败，请重试')
        error.value = message
        inputs.forEach(item => fail(item, message))
      }
      processed.value = output.size
    }
  } catch (exception) {
    if (!signal.aborted) {
      error.value = getLocalizedErrorMessage(exception, '读取文件列表失败')
      currentTargets.filter(item => !output.has(item.id)).forEach(item => fail(item, error.value))
    }
  } finally {
    if (!signal.aborted) {
      results.value = currentTargets.map(item => output.get(item.id)).filter(Boolean)
      processed.value = results.value.length
      busy.value = false
      emit('state', { busy: false, items: successful.value })
    }
  }
}
</script>

<style scoped>
.pending-file-counts { display: grid; gap: 8px; margin: 12px 0; }
.count-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.count-actions span { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
