<template>
  <span class="chat-project-managers" @mousedown.stop @dblclick.stop>
    <el-popover v-if="projectType === 'annotation' && canAdjust" v-model:visible="clientMenuVisible" trigger="click" placement="bottom-start" :width="200" :z-index="popoverZ"><template #reference><button type="button" class="chat-project-managers__more" aria-label="客户经理操作" @click="popoverZ = chatOverlayZIndex($event.currentTarget)">客户经理：{{ loading ? '加载中…' : clientManager }} ▾</button></template><div class="chat-project-managers__list"><el-button link @click="editManagers($event, 'client_manager')">编辑</el-button><el-button link @click="clientMenuVisible=false; transferVisible=true">交接与记录</el-button></div></el-popover>
    <span v-else>客户经理：{{ loading ? '加载中…' : clientManager }}</span>
    <el-popover v-if="projectType === 'annotation' && canAdjust" v-model:visible="menuVisible" trigger="click" placement="bottom-start" :width="200" :z-index="popoverZ">
      <template #reference><button type="button" class="chat-project-managers__more" aria-label="项目经理操作" :title="names.join('、')" @click="popoverZ = chatOverlayZIndex($event.currentTarget)">项目经理：{{ loading ? '加载中…' : names.length > 1 ? `${names[0]} 等 ${names.length} 人` : names[0] || '未设置' }} ▾</button></template>
      <div class="chat-project-managers__list"><span v-for="(name, index) in names" :key="index">{{ name }}</span><el-button link @click="editManagers">编辑</el-button><el-button link @click="menuVisible=false; transferVisible=true">交接与记录</el-button></div>
    </el-popover>
    <span v-else>项目经理：<span v-if="names.length < 2">{{ loading ? '加载中…' : names[0] || '未设置' }}</span><el-popover v-else trigger="click" placement="bottom-start" :width="240" :z-index="popoverZ"><template #reference><button type="button" class="chat-project-managers__more" @click="popoverZ = chatOverlayZIndex($event.currentTarget)">{{ names[0] }} 等 {{ names.length }} 人 ▾</button></template><div class="chat-project-managers__list"><strong>项目经理（{{ names.length }} 人）</strong><span v-for="(name, index) in names" :key="index">{{ name }}</span></div></el-popover></span>
    <button v-if="error" type="button" class="chat-project-managers__more" @click="load">加载失败，重试</button>
  </span>
  <ChatAnnotationManagers v-if="projectType === 'annotation' && canAdjust" :key="projectId" ref="managerEditor" :project-id="projectId" :manager-role="editorRole" hide-trigger />
  <AnnotationManagerTransferDialog v-if="transferVisible" v-model="transferVisible" :z-index="popoverZ+10" :can-transfer="isSuperAdmin()" @transferred="managersTransferred" />
</template>
<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ChatAnnotationManagers from './ChatAnnotationManagers.vue'
import { hasPermission, isSuperAdmin } from '@/utils/permission'
import { getAnnotationProject } from '@/api/annotationProjects'
import { getProject } from '@/api/projects'
import { subscribeAnnotationManagersUpdated, notifyAnnotationManagersUpdated } from '@/utils/annotationManagerSync'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
const props = defineProps({ projectId: { type: String, required: true }, projectType: { type: String, required: true } })
const AnnotationManagerTransferDialog = defineAsyncComponent(() => import('@/components/annotation/AnnotationManagerTransferDialog.vue'))
const canAdjust = computed(() => hasPermission('projects:read') || hasPermission('projects:write'))
const menuVisible=ref(false), clientMenuVisible=ref(false), transferVisible=ref(false), managerEditor=ref(), editorRole=ref('project_manager')
async function editManagers(event, role='project_manager') { menuVisible.value=false; clientMenuVisible.value=false; editorRole.value=role; await nextTick(); managerEditor.value?.open(event) }
function managersTransferred() { notifyAnnotationManagersUpdated(props.projectId) }
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
<style scoped>
.chat-project-managers__list > .el-button{margin:0;justify-content:flex-start;min-height:28px}
</style>
