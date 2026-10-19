<template>
  <el-popover
    :trigger="trigger"
    :placement="placement"
    :popper-options="viewportPopperOptions"
    :width="760"
    :title="popoverTitle"
    :show-after="showAfter"
    :hide-after="hideAfter"
    :popper-class="popperClass"
    :teleported="teleported"
    @show="load"
    @hide="cancelInlineEdit(); materialsActive = false"
  >
    <template #reference>
      <slot name="reference">
        <el-button type="primary" link @click.stop>{{ referenceText || displayRow.orderNo || '查看详情' }}</el-button>
      </slot>
    </template>
    <AnnotationProjectDetailContent :row="displayRow" :loading="loading" :project-id="projectId" :history="history" :custom-fields="customFields" :editable="editable" :materials-active="materialsActive" :save-text-field="saveText" :save-custom-field="saveCustom" @conflict="load" />
  </el-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as annotationApi from '@/api/annotationProjects'
import * as annotationOpsApi from '@/api/annotationOps'
import AnnotationProjectDetailContent from './AnnotationProjectDetailContent.vue'
const materialsActive = ref(false)
import { useAnnotationCustomFields } from '@/composables/useAnnotationCustomFields'

const props = defineProps({
  projectId: { type: [String, Number], required: true },
  summary: { type: Object, default: () => ({}) },
  editable: { type: Boolean, default: false },
  referenceText: { type: String, default: '' },
  trigger: { type: String, default: 'click' },
  placement: { type: String, default: 'left' },
  title: { type: String, default: '' },
  showAfter: { type: Number, default: 0 },
  hideAfter: { type: Number, default: 200 },
  popperClass: { type: String, default: 'annotation-detail-popover' },
  teleported: { type: Boolean, default: true },
})
const emit = defineEmits(['updated'])
// 左侧空间不足或表格横向滚动后，详情浮层仍必须完整留在视口内。
const viewportPopperOptions = {
  modifiers: [{
    name: 'preventOverflow',
    options: { rootBoundary: 'viewport', altAxis: true, tether: false, padding: 16 },
  }],
}
const detail = ref(null), history = ref([]), loading = ref(false)
const { fields: customFields, load: loadCustomFields } = useAnnotationCustomFields('project')
const displayRow = computed(() => detail.value || props.summary || {})
const popoverTitle = computed(() => props.title || `${displayRow.value.orderNo || '标注项目'} 详情`)
const cancelInlineEdit = () => window.dispatchEvent(new CustomEvent('business-inline-text-edit', { detail: 'popover-hidden' }))
const load = async () => { materialsActive.value=true; loading.value=true; try { const [project, rows] = await Promise.all([annotationApi.getAnnotationProject(props.projectId), annotationOpsApi.getStatusHistory(props.projectId).catch(()=>[]), loadCustomFields().catch(()=>{})]); detail.value=project; history.value=rows } catch(error) { ElMessage.error(error.detail||'加载项目详情失败') } finally { loading.value=false } }
const saveText = async (field, value) => { const updated=await annotationApi.updateAnnotationProjectTextField(props.projectId,field,value,displayRow.value.updatedAt); detail.value=updated; emit('updated',updated); return updated }
const saveCustom = async (field, value) => { const updated=await annotationApi.updateAnnotationCustomTextField(props.projectId,field,value,displayRow.value.updatedAt); detail.value=updated; emit('updated',updated); return updated }
</script>
