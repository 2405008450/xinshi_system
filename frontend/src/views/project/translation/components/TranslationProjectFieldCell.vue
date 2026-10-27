<template>
<div v-if="column.key === 'orderNo'" class="order-no-actions">
            <BusinessDetailPopover
              :row="row"
              title="项目详情"
              :items="context.getTranslationClientDetailItems(context.projectDetailItems, row)"
              :status-label="context.getStatusLabel"
              :status-type="context.getStatusType"
              :editable="context.canWriteProjects && !context.deleteMode"
              :save-field="(field, value) => context.saveProjectTextField(row, field, value)"
              @conflict="context.fetchData"
            >
              <template #reference>
                <el-button type="primary" link class="order-no-link business-clickable-cell" :title="`${row.orderNo}（点击查看详情）`" @click.stop>
                  {{ row.orderNo }}
                </el-button>
              </template>
            </BusinessDetailPopover>
            <PathActionButtons v-if="context.canReadProjectFiles" @open="context.openOriginalPath(row)" @copy="context.copyOriginalPath(row)" />
          </div>
          <span v-else-if="column.key === 'sourceFileName'" class="project-name-ellipsis" :title="row.sourceFileName || '-'">{{ row.sourceFileName || '-' }}</span>
          <el-dropdown
            v-else-if="column.key === 'projectStatus' && context.canWriteProjects"
            trigger="click"
            :disabled="context.projectStatusSavingIds.has(row.id)"
            @command="(command) => context.changeProjectStatus(row, command)"
          >
            <el-tag
              :type="context.getStatusType(row.projectStatus)"
              size="small"
              class="status-switch-tag"
              :class="{ 'is-updating': context.projectStatusSavingIds.has(row.id) }"
              :title="context.normalizeStatus(row.projectStatus)==='arranged'?'右键查看项目安排和调整记录':''"
              @contextmenu="context.openArrangementFromStatus($event,row)"
            >
              <span class="status-switch-text">{{ context.getStatusLabel(row.projectStatus) }}</span>
              <el-icon class="status-switch-caret"><CaretBottom /></el-icon>
            </el-tag>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="item in context.projectStatusOptions"
                  :key="item.value"
                  :command="item.value"
                  :disabled="item.value === context.normalizeStatus(row.projectStatus) || item.value === 'pending_confirmation' || context.projectStatusSavingIds.has(row.id)"
                >
                  <span class="status-option-row">
                    <el-tag :type="context.getStatusType(item.value)" size="small" effect="plain" class="status-option-tag">{{ item.label }}</el-tag>
                    <el-icon v-if="item.value === context.normalizeStatus(row.projectStatus)" class="status-current-icon"><Check /></el-icon>
                  </span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tag v-else-if="column.key === 'projectStatus'" :type="context.getStatusType(row.projectStatus)" :title="context.normalizeStatus(row.projectStatus)==='arranged'?'右键查看项目安排和调整记录':''" @contextmenu="context.openArrangementFromStatus($event,row)">
            {{ context.getStatusLabel(row.projectStatus) }}
          </el-tag>
          <DeadlineHintCell
            v-else-if="column.key === 'customerDeadlineTime'"
            :deadline="row.customerDeadlineTime"
            :status="row.projectStatus"
          />
          <TranslatorCompletionPopover
            v-else-if="column.key === 'translatorReturnTime'"
            :translators="row.assignedTranslators"
            :status="row.projectStatus"
            :editable="context.canWriteProjects && !context.deleteMode"
            :save="(completions) => context.saveProjectTranslatorCompletions(row, completions)"
          />
          <div
            v-else-if="column.key === 'languagePair'"
            class="compact-cell-value"
            :title="row.languagePair || '-'"
          >
            <span class="compact-cell-value__primary">{{ context.getLanguagePairSummary(row.languagePair).primary }}</span>
            <span v-if="context.getLanguagePairSummary(row.languagePair).extraCount" class="compact-cell-value__count">
              +{{ context.getLanguagePairSummary(row.languagePair).extraCount }}
            </span>
          </div>
          <div
            v-else-if="column.key === 'assignedTranslators'"
            class="compact-cell-value"
            :title="context.formatAssignedTranslators(row.assignedTranslators, row.translatorName)"
          >
            <span class="compact-cell-value__primary">{{ context.getAssignedTranslatorSummary(row).primary }}</span>
            <span v-if="context.getAssignedTranslatorSummary(row).extraCount" class="compact-cell-value__count">
              +{{ context.getAssignedTranslatorSummary(row).extraCount }}
            </span>
          </div>
          <div v-else-if="column.key === 'wordCountMatrix'" class="word-count-list-cell">
            <WordCountMatrixPopover
              v-model="row.wordCountMatrix"
              entity-type="project"
              :entity-id="row.id"
              title="项目字数统计"
              @saved="context.fetchData"
            >
              <template #reference>
                <el-button type="primary" link class="word-count-compact-link business-clickable-cell" :title="context.getWordCountListSummary(row).title">
                  <span class="compact-cell-value">
                    <span class="compact-cell-value__primary">{{ context.getWordCountListSummary(row).primary }}</span>
                    <span v-if="context.getWordCountListSummary(row).extraCount" class="compact-cell-value__count">
                      +{{ context.getWordCountListSummary(row).extraCount }}
                    </span>
                  </span>
                </el-button>
              </template>
            </WordCountMatrixPopover>
          </div>
          <span v-else>{{ context.formatTableColumnValue(row, column) }}</span>
</template>
<script setup>
import {CaretBottom,Check} from '@element-plus/icons-vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import PathActionButtons from '@/components/common/PathActionButtons.vue'
import DeadlineHintCell from '@/components/common/DeadlineHintCell.vue'
import WordCountMatrixPopover from '@/components/common/WordCountMatrixPopover.vue'
import TranslatorCompletionPopover from './TranslatorCompletionPopover.vue'
defineProps({row:{type:Object,required:true},column:{type:Object,required:true},context:{type:Object,required:true}})
</script>
<style scoped>
.order-no-actions { display: flex; align-items: center; gap: 6px; }
.order-no-actions :deep(.el-popover__reference-wrapper) { flex: 1; min-width: 0; }
.order-no-link,
.sub-order-no-link { display: block; width: 100%; height: auto; min-width: 0; padding: 0; overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.status-switch-tag.el-tag { display: inline-flex; align-items: center; gap: 4px; flex-wrap: nowrap; max-width: 100%; cursor: pointer; user-select: none; vertical-align: middle; transition: opacity 0.15s ease; }
.status-switch-tag :deep(.el-tag__content) { display: inline-flex; align-items: center; gap: 4px; flex-wrap: nowrap; white-space: nowrap; line-height: 1; }
.status-switch-text { line-height: 1; }
.status-switch-caret { width: 10px; height: 10px; flex-shrink: 0; margin: 0; font-size: 10px; }
.status-switch-tag:hover { opacity: 0.85; }
.status-switch-tag.is-updating { pointer-events: none; opacity: 0.55; }
.status-option-row { display: inline-flex; align-items: center; gap: 8px; width: 100%; }
.status-current-icon { color: var(--el-color-primary); }
.compact-cell-value { display: flex; align-items: center; min-width: 0; gap: 5px; white-space: nowrap; }
.compact-cell-value__primary { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.compact-cell-value__count { flex-shrink: 0; padding: 0 5px; border-radius: 8px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 12px; line-height: 18px; }

.word-count-list-cell { display: flex; align-items: center; min-width: 0; }
.word-count-compact-link { max-width: 100%; height: auto; padding: 0; }
.word-count-compact-link :deep(.compact-cell-value) { max-width: 100%; }
.word-count-compact-link :deep(.compact-cell-value__primary) { color: inherit; }

.project-name-ellipsis{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

</style>
