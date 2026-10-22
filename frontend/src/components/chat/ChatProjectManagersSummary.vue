<template>
  <span class="chat-project-managers" @mousedown.stop @dblclick.stop>
    <span>客户经理：{{ loading ? '加载中…' : clientManager }}</span>
    <span>项目经理：<span v-if="names.length < 2">{{ loading ? '加载中…' : names[0] || '未设置' }}</span><el-popover v-else trigger="click" placement="bottom-start" :width="240" :z-index="popoverZ"><template #reference><button type="button" class="chat-project-managers__more" @click="popoverZ = chatOverlayZIndex($event.currentTarget)">{{ names[0] }} 等 {{ names.length }} 人 ▾</button></template><div class="chat-project-managers__list"><strong>项目经理（{{ names.length }} 人）</strong><span v-for="(name, index) in names" :key="index">{{ name }}</span></div></el-popover></span>
    <button v-if="error" type="button" class="chat-project-managers__more" @click="load">加载失败，重试</button>
  </span>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getAnnotationProject } from '@/api/annotationProjects'
import { getProject } from '@/api/projects'
import { subscribeAnnotationManagersUpdated } from '@/utils/annotationManagerSync'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
const props = defineProps({ projectId: { type: String, required: true }, projectType: { type: String, required: true } })
const project = ref(null), loading = ref(false), error = ref(false), popoverZ = ref(2120)
const clientManager = computed(() => project.value?.clientManagerName || project.value?.clientManager || '未设置')
const names = computed(() => {
  const rows = (project.value?.roleAssignments || []).filter(row => (row.roleCode || row.role_code) === 'project_manager' && (row.assigneeId || row.assignee_id))
  const unique = new Map(rows.map(row => [String(row.assigneeId || row.assignee_id), row.assigneeName || row.assignee_name || '未命名人员']))
  return unique.size ? [...unique.values()] : project.value?.projectManagerName ? [project.value.projectManagerName] : []
})
let controller, generation = 0
async function load() {
  controller?.abort(); controller = new AbortController(); const version = ++generation
  project.value = null; error.value = false; loading.value = true
  try {
    const result = await (props.projectType === 'annotation' ? getAnnotationProject : getProject)(props.projectId, { signal: controller.signal })
    if (version === generation) project.value = result
  } catch (e) { if (version === generation && e.code !== 'ERR_CANCELED') error.value = true }
  finally { if (version === generation) loading.value = false }
}
watch(() => [props.projectId, props.projectType], load, { immediate: true })
const unsubscribe = subscribeAnnotationManagersUpdated(id => { if (id === props.projectId) void load() })
onBeforeUnmount(() => { ++generation; controller?.abort(); unsubscribe() })
</script>
<style scoped>
.chat-project-managers{display:flex;align-items:center;flex-wrap:wrap;gap:3px 14px;font-size:11px;color:#64748b;line-height:1.5;user-select:text;cursor:text}.chat-project-managers__more{border:0;background:none;color:#2563eb;padding:0;font:inherit;cursor:pointer;text-decoration:underline;text-underline-offset:2px}.chat-project-managers__list{display:flex;flex-direction:column;gap:8px;max-height:220px;overflow-y:auto;font-size:12px}
</style>
