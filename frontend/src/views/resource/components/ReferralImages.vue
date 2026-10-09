<template>
  <div class="referral-images">
    <div v-for="item in images" :key="item.id" class="referral-image-card">
      <el-image v-if="urls[item.id]" :src="urls[item.id]" :preview-src-list="previewUrls" :initial-index="previewUrls.indexOf(urls[item.id])" preview-teleported fit="contain" :alt="item.name" />
      <div v-else class="referral-image-placeholder"><span>{{ failures[item.id] ? '图片加载失败' : '图片加载中…' }}</span><el-button v-if="failures[item.id]" link @click="load(item)">重试</el-button></div>
      <span class="referral-image-name" :title="item.name">{{ item.name }}</span>
      <el-tag v-if="showStatus" size="small" type="success" effect="plain">已保存</el-tag>
      <el-button v-if="editable" link type="danger" :disabled="disabled" @click="$emit('remove', item)">删除图片</el-button>
    </div>
    <span v-if="!images.length" class="referral-muted">暂无图片</span>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import { referralApi } from '@/api/referralDevelopment'
const props = defineProps({ images: { type: Array, default: () => [] }, editable: Boolean, disabled: Boolean, showStatus: Boolean })
defineEmits(['remove'])
const urls = reactive({}), failures = reactive({})
const controllers = new Map()
const previewUrls = computed(() => props.images.map(i => urls[i.id]).filter(Boolean))
async function load(item) {
  if (controllers.has(item.id) || urls[item.id]) return
  const controller = new AbortController(); controllers.set(item.id, controller); delete failures[item.id]
  try {
    const blob = await referralApi.image(item.id, controller.signal)
    if (!controller.signal.aborted && props.images.some(i => i.id === item.id)) urls[item.id] = URL.createObjectURL(blob)
  } catch (e) { if (!controller.signal.aborted) failures[item.id] = true }
  finally { controllers.delete(item.id) }
}
watch(() => props.images.map(i => i.id).join(','), () => {
  const ids = new Set(props.images.map(i => i.id))
  for (const id of Object.keys(urls)) if (!ids.has(id)) { URL.revokeObjectURL(urls[id]); delete urls[id] }
  for (const [id, controller] of controllers) if (!ids.has(id)) controller.abort()
  props.images.forEach(load)
}, { immediate: true })
onBeforeUnmount(() => { controllers.forEach(c => c.abort()); Object.values(urls).forEach(URL.revokeObjectURL) })
</script>

<style scoped>
.referral-images{display:flex;gap:12px;flex-wrap:wrap}.referral-image-card{width:132px;display:flex;flex-direction:column;gap:5px;align-items:center}.referral-image-card .el-image,.referral-image-placeholder{width:132px;height:118px;border:1px solid #e2e8f0;border-radius:6px}.referral-image-placeholder{display:flex;flex-direction:column;justify-content:center;align-items:center;color:#64748b;font-size:12px}.referral-image-name{width:100%;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;font-size:12px}.referral-muted{color:#64748b;font-size:13px}
</style>
