<template>
  <el-popover
    v-model:visible="visible"
    trigger="click"
    placement="left"
    :width="680"
    popper-class="translator-completion-popover"
    :disabled="!normalizedTranslators.length"
    @show="resetDraft"
    @hide="resetDraft"
  >
    <template #reference>
      <button
        type="button"
        class="translator-return-trigger business-clickable-cell"
        :class="{ 'is-disabled': !normalizedTranslators.length }"
        :title="normalizedTranslators.length ? '点击编辑译员任务完成情况及价格' : '暂无已指派译员'"
        @click.stop
      >
        <div v-if="deadlineItems.length" class="translator-return-deadlines">
          <div v-for="item in deadlineItems" :key="item.arrangementId" class="translator-return-deadline">
            <span class="translator-return-deadline__name">{{ item.translatorName }}</span>
            <DeadlineHintCell :deadline="item.returnTime" :status="status" mode="translator" />
          </div>
        </div>
        <span v-else>-</span>
      </button>
    </template>

    <div class="translator-completion-panel">
      <div class="translator-completion-panel__header">
        <strong>译员任务完成情况及价格</strong>
        <span>完成情况、单价和总价与当前项目对应的派稿任务绑定</span>
      </div>

      <div class="translator-completion-panel__body">
        <div v-for="item in draft" :key="item.arrangementId" class="translator-completion-row">
          <div class="translator-completion-row__meta">
            <strong>{{ item.translatorName }}</strong>
            <span>回稿时间：{{ formatDateTime(item.returnTime) }}</span>
          </div>
          <div class="translator-completion-row__fields">
            <div class="translator-completion-row__prices">
              <label class="translator-completion-field">
                <span>译员单价</span>
                <el-input-number
                  v-if="editable"
                  v-model="item.translatorUnitPrice"
                  :min="0"
                  :precision="4"
                  :controls="false"
                  placeholder="请输入单价"
                />
                <div v-else class="translator-completion-row__readonly">
                  {{ formatTranslatorPrice(item.translatorUnitPrice, 4) }}
                </div>
              </label>
              <label class="translator-completion-field">
                <span>译员总价</span>
                <el-input-number
                  v-if="editable"
                  v-model="item.translatorTotalPrice"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  placeholder="请输入总价"
                />
                <div v-else class="translator-completion-row__readonly">
                  {{ formatTranslatorPrice(item.translatorTotalPrice, 2) }}
                </div>
              </label>
            </div>
            <label class="translator-completion-field">
              <span>任务完成情况</span>
              <el-input
                v-if="editable"
                v-model="item.completionRemarks"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 4 }"
                maxlength="255"
                show-word-limit
                clearable
                placeholder="请输入该译员的任务完成情况"
              />
              <div v-else class="translator-completion-row__readonly">
                {{ item.completionRemarks || '-' }}
              </div>
            </label>
          </div>
        </div>
      </div>

      <div class="translator-completion-panel__footer">
        <el-button @click="visible = false">{{ editable ? '取消' : '关闭' }}</el-button>
        <el-button v-if="editable" type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import { formatBusinessDateTime } from '@/utils/deadlineDisplay'
import {
  buildTranslatorAssignmentDetailUpdates,
  formatTranslatorPrice,
  normalizeTranslatorAssignmentDetails,
} from '@/utils/translatorAssignmentDetails'

const props = defineProps({
  translators: { type: Array, default: () => [] },
  status: { type: String, default: '' },
  editable: { type: Boolean, default: false },
  save: { type: Function, default: null },
})

const emit = defineEmits(['saved'])
const visible = ref(false)
const saving = ref(false)
const draft = ref([])

const normalizedTranslators = computed(() => normalizeTranslatorAssignmentDetails(props.translators))

const deadlineItems = computed(() => normalizedTranslators.value.filter((item) => item.returnTime))
const formatDateTime = (value) => value ? formatBusinessDateTime(value) : '-'

const resetDraft = () => {
  draft.value = normalizedTranslators.value.map((item) => ({ ...item }))
}

const handleSave = async () => {
  if (!props.save || saving.value) return
  saving.value = true
  try {
    const details = buildTranslatorAssignmentDetailUpdates(draft.value)
    const updated = await props.save(details)
    emit('saved', updated)
    ElMessage.success('译员任务完成情况及价格已保存')
    visible.value = false
  } catch (error) {
    ElMessage.error(error?.detail || '译员任务完成情况及价格保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style>
.translator-completion-popover { max-width: calc(100vw - 32px) !important; }
.translator-return-trigger { width: 100%; padding: 0; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; }
.translator-return-trigger:hover { color: var(--el-color-primary); }
.translator-return-trigger.is-disabled { cursor: default; }
.translator-return-trigger.is-disabled:hover { color: inherit; }
.translator-return-deadlines { display: flex; min-width: 0; flex-direction: column; gap: 4px; }
.translator-return-deadline { display: grid; grid-template-columns: max-content minmax(0, 1fr); align-items: start; gap: 5px; }
.translator-return-deadline__name { max-width: 72px; overflow: hidden; padding-top: 2px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.translator-completion-panel__header { display: flex; flex-direction: column; gap: 4px; padding-bottom: 12px; border-bottom: 1px solid var(--el-border-color-lighter); }
.translator-completion-panel__header span { color: var(--el-text-color-secondary); font-size: 12px; }
.translator-completion-panel__body { display: flex; max-height: min(460px, calc(100vh - 210px)); flex-direction: column; gap: 14px; padding: 14px 2px; overflow-y: auto; }
.translator-completion-row { display: grid; grid-template-columns: minmax(140px, 190px) minmax(0, 1fr); align-items: start; gap: 12px; }
.translator-completion-row__meta { display: flex; min-width: 0; flex-direction: column; gap: 4px; }
.translator-completion-row__meta strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.translator-completion-row__meta span { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.translator-completion-row__fields { display: flex; min-width: 0; flex-direction: column; gap: 10px; }
.translator-completion-row__prices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.translator-completion-field { display: flex; min-width: 0; flex-direction: column; gap: 5px; }
.translator-completion-field > span { color: var(--el-text-color-regular); font-size: 12px; line-height: 18px; }
.translator-completion-field .el-input-number { width: 100%; }
.translator-completion-row__readonly { min-height: 32px; padding: 6px 10px; border-radius: 4px; background: var(--el-fill-color-light); line-height: 20px; white-space: pre-wrap; word-break: break-word; }
.translator-completion-panel__footer { display: flex; justify-content: flex-end; gap: 8px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); }
@media (max-width: 640px) {
  .translator-completion-row { grid-template-columns: 1fr; gap: 6px; }
  .translator-completion-row__prices { grid-template-columns: 1fr; }
}
</style>
