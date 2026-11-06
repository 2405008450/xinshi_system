<template>
  <BusinessDetailPopover
    :row="details"
    :title="isProject ? '项目详情' : '子订单详情'"
    :items="detailItems"
    :loading="loading"
    :status-label="statusLabel"
    @show="loadDetails"
    @hide="cancelLoad"
  >
    <template #reference>
      <el-button link type="primary" class="order-detail-link" :title="`${order.orderNo}（点击查看详情）`" @click.stop>{{ order.orderNo }}</el-button>
    </template>
  </BusinessDetailPopover>
</template>

<script setup>
import {useProjectStatusSync} from '@/composables/useProjectStatusSync'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import BusinessDetailPopover from './BusinessDetailPopover.vue'
import { getProject } from '@/api/projects'
import { getSubOrder } from '@/api/subOrders'
import { translationProjectDetailItems, translationSubOrderDetailItems } from '@/utils/translationProjectDetail'
import { getTranslationClientDetailItems } from '@/utils/translationClientLabels'
import { getProjectStatusLabel } from '@/utils/projectStatus'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({ order: { type: Object, required: true } })
const details = ref({})
const loading = ref(false)
const isProject = computed(() => props.order.id === props.order.rootId)
const detailItems = computed(() => isProject.value
  ? getTranslationClientDetailItems(translationProjectDetailItems, details.value)
  : translationSubOrderDetailItems)
const statusLabel = value => getProjectStatusLabel('translation', value)
let sequence = 0
function cancelLoad() { sequence++; loading.value = false }
watch(() => props.order, cancelLoad)
onBeforeUnmount(cancelLoad)

async function loadDetails() {
  const current = ++sequence
  // Each opening reads the source order so edits elsewhere cannot leave a stale detail cache.
  details.value = {}
  loading.value = true
  try {
    const result = await (isProject.value ? getProject(props.order.id) : getSubOrder(props.order.id))
    if (current === sequence) details.value = result
  } catch (error) {
    if (current === sequence) ElMessage.error(getLocalizedErrorMessage(error, '订单详情加载失败'))
  } finally {
    if (current === sequence) loading.value = false
  }
}
useProjectStatusSync('translation',details,{enabled:()=>isProject.value})
useProjectStatusSync('translation_suborder',details,{field:'status',enabled:()=>!isProject.value})
</script>

<style scoped>
.order-detail-link { max-width: 100%; height: auto; white-space: normal; text-align: left; }
.order-detail-link :deep(span) { overflow-wrap: anywhere; }
</style>
