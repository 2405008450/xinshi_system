<template>
  <span v-if="orderNo && ['annotation', 'translation'].includes(projectType)" class="chat-order-identity" :class="{ 'is-child': childOrder, 'has-title': title }">
    <button v-if="title && showManagers && projectId && projectType === 'annotation'" type="button" class="chat-order-identity__title chat-order-identity__link" :title="`${title} · 点击查看项目进度`" aria-label="查看项目进度" @mousedown.stop @dblclick.stop @click.stop="progressVisible=true">{{ title }}</button>
    <strong v-else-if="title" class="chat-order-identity__title" :title="title">{{ title }}</strong>
    <span class="chat-order-identity__details">
      <b v-if="childOrder" class="chat-order-identity__badge">{{ orderDepth > 1 ? '孙订单' : '子订单' }}</b>
      <ChatProjectActions v-if="showManagers && projectId" :project-id="projectId" :project-type="projectType" hide-materials><template #detail-reference><button type="button" class="chat-order-identity__number chat-order-identity__link" :title="`订单号：${orderNo} · 点击查看项目详情`" :aria-label="`查看项目详情 ${orderNo}`" @mousedown.stop @dblclick.stop @click.stop>{{ orderNo }}</button></template></ChatProjectActions>
      <span v-else class="chat-order-identity__number" :title="`订单号：${orderNo}`">{{ orderNo }}</span>
      <ChatProjectActions v-if="showManagers && projectId && projectType === 'annotation'" :project-id="projectId" :project-type="projectType" hide-details icon-only />
      <ChatProjectManagersSummary v-if="showManagers && projectId" :project-id="projectId" :project-type="projectType" />
    </span>
  </span>
  <el-config-provider v-if="progressVisible" :z-index="10000"><AnnotationProgressHost :key="projectId" embedded progress-only :progress-project-id="projectId" @progress-closed="progressVisible=false" /></el-config-provider>
</template>
<script setup>
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import ChatProjectManagersSummary from './ChatProjectManagersSummary.vue'
import ChatProjectActions from './ChatProjectActions.vue'
const AnnotationProgressHost = defineAsyncComponent(() => import('@/views/project/AnnotationProjects.vue'))
const progressVisible = ref(false)
const props = defineProps({ orderNo: { type: String, default: '' }, projectType: { type: String, default: '' }, title: { type: String, default: '' }, projectId: { type: String, default: '' }, showManagers: Boolean })
watch(()=>props.projectId,()=>{progressVisible.value=false})
const orderDepth = computed(() => /^AP-\d{6}-\d+(?:\.\d{3}){1,2}$/.test(props.orderNo) ? props.orderNo.split('.').length - 1 : 0)
const childOrder = computed(() => props.projectType === 'annotation' && orderDepth.value > 0)
</script>
<style scoped>
.chat-order-identity{display:flex;min-width:0;flex-direction:column;gap:5px;user-select:text;cursor:text}
.chat-order-identity__title{display:block;font-size:13px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-order-identity__details{display:flex;align-items:center;flex-wrap:wrap;gap:5px;font-size:11px;color:#64748b;line-height:1.5}
.chat-order-identity__number{overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.chat-order-identity__badge{flex:none;padding:1px 6px;border:1px solid #f59e0b;border-radius:4px;background:#fef3c7;color:#92400e;font-size:11px}
.is-child .chat-order-identity__number{color:#92400e;font-weight:600}
.has-title{gap:2px;min-width:0}
.chat-order-identity__link{border:0;background:transparent;padding:0;margin:0;color:inherit;font:inherit;text-align:left;cursor:pointer;user-select:text}
.chat-order-identity__title.chat-order-identity__link{font-size:13px;font-weight:700;line-height:1.5}
.chat-order-identity__link:hover{text-decoration:underline;text-underline-offset:2px}
.chat-order-identity__link:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:2px}
</style>
