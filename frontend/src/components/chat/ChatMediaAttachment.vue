<template>
  <div class="chat-media">
    <div class="chat-media-name">{{ file.originalName }} · {{ sizeLabel(file.fileSize) }}</div>
    <video v-if="url && file.contentType.startsWith('video/')" ref="player" :src="url" controls preload="metadata" @error="playbackError = true" />
    <audio v-else-if="url" ref="player" :src="url" controls preload="metadata" @error="playbackError = true" />
    <div>
      <el-button v-if="!url" link type="primary" :loading="loading" @click="load(false)">{{ error ? '重新加载' : '加载播放' }}</el-button>
      <el-button link type="primary" :disabled="loading" @click="load(true)">下载</el-button>
    </div>
    <small v-if="error" role="alert">{{ error }}</small>
    <small v-if="playbackError" role="alert">浏览器无法播放此编码，请下载后播放。</small>
  </div>
</template>
<script setup>
import { ref, onBeforeUnmount, watch } from 'vue'
const props = defineProps({ file: { type: Object, required: true }, fetchBlob: { type: Function, required: true }, sizeLabel: { type: Function, required: true }, active: Boolean })
const url = ref(''), loading = ref(false), error = ref(''), playbackError = ref(false), player = ref()
let controller, pending, disposed = false
function save() {
  const link = document.createElement('a'); link.href = url.value; link.download = props.file.originalName; link.click()
}
async function load(download) {
  if (url.value) { if (download) save(); return }
  if (pending) return
  controller = new AbortController(); const current = controller
  loading.value = true; error.value = ''
  pending = props.fetchBlob(props.file, current.signal)
  try {
    const blob = await pending
    if (disposed || current.signal.aborted) return
    url.value = URL.createObjectURL(blob)
    if (download) save()
  } catch (e) {
    if (!current.signal.aborted) error.value = typeof e?.message === 'string' ? `附件加载失败：${e.message}` : '附件加载失败，请重试'
  } finally { if (controller === current) { loading.value = false; pending = null } }
}
function release() {
  controller?.abort(); controller = null; pending = null; loading.value = false
  player.value?.pause(); player.value?.removeAttribute('src'); player.value?.load()
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''; error.value = ''; playbackError.value = false
}
watch(() => props.active, active => { if (!active) release() })
onBeforeUnmount(() => { disposed = true; release() })
</script>
<style scoped>
.chat-media{display:flex;flex-direction:column;gap:6px;max-width:100%;min-width:0}.chat-media-name{overflow-wrap:anywhere;font-size:12px}.chat-media video{width:360px;max-width:100%;max-height:280px}.chat-media audio{width:300px;max-width:100%}.chat-media small{color:var(--el-color-danger)}
</style>
