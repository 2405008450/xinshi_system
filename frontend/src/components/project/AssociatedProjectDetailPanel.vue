<template>
  <section class="associated-project-detail" :aria-label="title" v-loading="state.loading">
    <header class="associated-project-detail__header">
      <strong>{{ title }}</strong>
      <div class="associated-project-detail__actions">
        <el-button v-if="state.detail" link type="primary" @click="$emit('enter')">进入项目</el-button>
        <el-button link @click="$emit('close')">{{ mobile ? backLabel : '关闭' }}</el-button>
      </div>
    </header>
    <div class="associated-project-detail__body">
      <el-alert v-if="state.error" :title="state.error" type="warning" :closable="false"><el-button link type="primary" @click="$emit('retry')">重新加载</el-button></el-alert>
      <template v-if="state.detail">
        <el-alert v-for="warning in state.extras.warnings || []" :key="warning" :title="warning" type="warning" :closable="false"><el-button link type="primary" @click="$emit('retry')">重新加载</el-button></el-alert>
        <AnnotationProjectDetailContent v-if="sourceType === 'annotation'" :row="state.detail" :project-id="projectId" :history="state.extras.history" :custom-fields="state.extras.customFields" :materials="state.extras.materials" :materials-error="state.extras.materialsError" :allow-nested-details="false" />
        <InterpretationProjectDetailContent v-else-if="sourceType === 'interpretation'" :row="state.detail" />
        <BusinessDetailContent v-else :row="state.detail" :items="items" :status-label="statusLabel" :status-type="statusType">
          <template v-if="sourceType==='translation'" #field-wordCountMatrix="{value}">
            <WordCountMatrixPopover :entity-id="projectId" entity-type="project" read-only>
              <template #reference><el-button link type="primary" class="associated-project-workload" aria-label="查看工作量统计表单">{{value}} · 查看工作量表单</el-button></template>
            </WordCountMatrixPopover>
          </template>
        </BusinessDetailContent>
      </template>
      <p v-else-if="state.loading" class="associated-project-detail__hint">正在加载项目详情…</p>
    </div>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import AnnotationProjectDetailContent from '@/components/annotation/AnnotationProjectDetailContent.vue'
import InterpretationProjectDetailContent from './InterpretationProjectDetailContent.vue'
import BusinessDetailContent from '@/components/common/BusinessDetailContent.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import { translationProjectDetailItems } from '@/utils/translationProjectDetail'
import { recruitmentProjectDetailItems } from '@/utils/recruitmentProjectDetail'
import { getTranslationClientDetailItems } from '@/utils/translationClientLabels'
import { getProjectStatusLabel, getProjectStatusType } from '@/utils/projectStatus'
const props = defineProps({ sourceType: String, projectId: String, state: { type: Object, required: true }, title: String, mobile: Boolean, backLabel: { type: String, default: '返回资源需求' } })
defineEmits(['close', 'retry', 'enter'])
const pathFields = [
  ['storage_path','原文路径'],['dispatch_path','派稿文路径'],['translation_path','译文路径'],
  ['translator_return_path','译员发回路径'],['client_delivery_path','发客户路径'],
  ['project_feedback_path','项目反馈路径'],['feedback_delivery_path','反馈后发客户路径'],
]
const items = computed(() => {
  if (props.sourceType !== 'translation') return recruitmentProjectDetailItems
  const paths = [
    {key:'networkFilePath',label:'项目路径',span:2},
    ...pathFields.map(([key,label])=>({key,label,span:2,valueGetter:()=>props.state.extras.pathGroup?.[key]})),
    {key:'referenceFilePathOne',label:'参考文件路径一',span:2},
  ]
  return getTranslationClientDetailItems(translationProjectDetailItems.flatMap(item=>item.key==='wordCountMatrix'?[item,...paths]:[item]), props.state.detail)
})
const statusLabel = value => getProjectStatusLabel(props.sourceType, value)
const statusType = value => getProjectStatusType(props.sourceType, value)
</script>
<style>
.associated-project-popover { width: min(760px, calc(100vw - 32px)) !important; max-width: calc(100vw - 32px); }
.associated-project-detail__header { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--el-border-color-lighter); }
.associated-project-detail__actions { display: flex; flex-shrink: 0; align-items: center; gap: 10px; }
.associated-project-detail__actions .el-button + .el-button { margin-left: 0; }
.associated-project-detail__body { max-height: min(500px, calc(100vh - 200px)); overflow-y: auto; overscroll-behavior: contain; padding-top: 10px; overflow-wrap: anywhere; }
.associated-project-detail__body .business-detail-popover__content, .associated-project-detail__body .annotation-project-detail__content, .associated-project-detail__body .detail-content { max-height: none; overflow: visible; }
.associated-project-detail__body .el-alert { margin-bottom: 10px; }
.associated-project-detail__hint { min-height: 70px; color: var(--el-text-color-secondary); }
.associated-project-workload{white-space:normal;text-align:left;height:auto;line-height:1.5}
@media (max-width: 768px) {
  .associated-project-detail__body .el-descriptions__table { table-layout: fixed; }
  .associated-project-detail__body .el-descriptions__label { width: 72px; min-width: 72px; white-space: normal; }
  .associated-project-detail__body .el-descriptions__cell { padding: 6px; font-size: 12px; word-break: break-word; }
}
</style>
