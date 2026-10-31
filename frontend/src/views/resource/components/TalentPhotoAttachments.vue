<template>
  <div v-if="attachments.length" class="talent-photo-attachments">
    <div v-for="item in attachments" :key="item.id" class="talent-photo-attachment">
      <template v-if="!audio">
        <el-image v-if="urls[item.id]" :src="urls[item.id]" :preview-src-list="previewUrls" :initial-index="previewUrls.indexOf(urls[item.id])" preview-teleported fit="contain" :alt="item.originalName" />
        <div v-else class="talent-photo-placeholder">
          <span>{{ failures[item.id] ? '图片加载失败' : '图片加载中…' }}</span>
          <el-button v-if="failures[item.id]" link type="primary" @click="load(item)">重试</el-button>
        </div>
      </template>
      <span class="talent-photo-name" :title="item.originalName">{{ item.originalName }}</span>
      <el-button link type="primary" @click="download(item)">下载</el-button>
    </div>
  </div>
  <span v-else>-</span>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getTalentAttachmentBlob } from '@/api/talents'

const props = defineProps({ personId: String, attachments: { type: Array, default: () => [] }, audio: Boolean })
const urls = reactive({}), failures = reactive({})
const controllers = new Map()
const previewUrls = computed(() => props.attachments.map(item => urls[item.id]).filter(Boolean))

async function load(item) {
  if (!props.personId || controllers.has(item.id) || urls[item.id]) return
  const controller = new AbortController()
  controllers.set(item.id, controller)
  delete failures[item.id]
  try {
    const blob = await getTalentAttachmentBlob(props.personId, item.id, { signal: controller.signal })
    if (!controller.signal.aborted && props.attachments.some(file => file.id === item.id)) {
      urls[item.id] = URL.createObjectURL(blob)
    }
  } catch {
    if (!controller.signal.aborted) failures[item.id] = true
  } finally {
    if (controllers.get(item.id) === controller) controllers.delete(item.id)
  }
}

async function download(item) {
  try {
    const blob = await getTalentAttachmentBlob(props.personId, item.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = item.originalName
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch {
    ElMessage.error('附件下载失败')
  }
}

watch(() => [props.personId, props.audio, ...props.attachments.map(item => item.id)], (current, previous) => {
  const personChanged = previous && current[0] !== previous[0]
  const ids = new Set(props.audio ? [] : props.attachments.map(item => item.id))
  for (const id of Object.keys(urls)) {
    if (!personChanged && ids.has(id)) continue
    URL.revokeObjectURL(urls[id])
    delete urls[id]
  }
  for (const [id, controller] of controllers) {
    if (!personChanged && ids.has(id)) continue
    controller.abort()
    controllers.delete(id)
  }
  if (!props.audio) props.attachments.forEach(load)
}, { immediate: true })

onBeforeUnmount(() => {
  controllers.forEach(controller => controller.abort())
  Object.values(urls).forEach(URL.revokeObjectURL)
})
</script>

<style scoped>
.talent-photo-attachments{display:flex;flex-wrap:wrap;gap:12px}
.talent-photo-attachment{display:flex;flex-direction:column;align-items:flex-start;gap:4px;width:140px;min-width:0}
.talent-photo-attachment .el-image,.talent-photo-placeholder{width:132px;max-width:100%;height:118px;border:1px solid #e2e8f0;border-radius:6px}
.talent-photo-placeholder{display:flex;flex-direction:column;align-items:center;justify-content:center;color:#64748b;font-size:12px}
.talent-photo-name{max-width:100%;overflow-wrap:anywhere;font-size:12px}
</style>
