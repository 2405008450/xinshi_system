<template>
  <div class="resource-request-page">
    <component v-if="!editorOnly" :is="embedded ? 'section' : ElCard" :class="embedded ? 'resource-request-panel' : 'common-page-card compact-list-card'">
      <div class="resource-request-toolbar">
        <div class="header">
          <div v-if="!embedded || arrangementMode">
            <h2>{{ arrangementMode ? '需求管理' : '资源需求管理' }}</h2>
            <p v-if="!arrangementMode">统一跟踪标注、招聘、口译、笔译及其他资源请求</p>
          </div>
          <div class="header-actions">
            <el-button v-if="!deleteMode" @click="openNotes">需求说明</el-button>
            <TableColumnSettings settings-key="resource-requests"
              v-model="selectedColumnKeys"
              :columns="tableColumns"
              :column-count="2"
              :hint="arrangementMode ? '序号、详情和操作列固定显示；客户编号等低频字段默认隐藏，可按需启用。' : '序号和操作列固定显示；客户编号等低频字段默认隐藏，可按需启用。'"
              @reset="resetColumns"
            />
            <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
            <el-button v-if="canWrite && !deleteMode" type="primary" @click="openEditor()">新增资源需求</el-button>
          </div>
        </div>
      </div>

      <AppForm :inline="true" :model="searchForm" class="search-form project-list-search-form">
        <div class="project-list-primary-filters">
          <el-form-item label="关键词" class="project-list-keyword-filter">
            <el-input
              v-model="searchForm.keyword"
              clearable
              placeholder="搜索需求编号、项目、客户或需求详情"
              @input="onKeyword"
              @keyup.enter="search"
            />
          </el-form-item>
          <el-form-item label="状态" class="project-list-status-filter">
            <el-select v-model="filterModel.requestStatus" multiple collapse-tags :max-collapse-tags="1" clearable placeholder="请求状态" @change="search">
              <el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item class="project-list-search-actions">
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
          <AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" popper-class="resource-request-advanced-popover" @clear="clearAdvanced" @reset="reset">
            <CompactFilterGrid :fields="advancedFilterFields" :model="filterModel" @update="updateConfiguredFilter" @text-input="onConfiguredText" @change="search" @enter="search" />
          </AdvancedFilterPopover>
        </el-form-item>
      </AppForm>

      <el-alert v-if="listError" class="list-error" type="error" show-icon :closable="false">
        <template #title>资源需求列表加载失败</template>
        <div class="list-error__content">
          <span>{{ listError }}</span>
          <el-button link type="primary" :loading="loading" @click="fetchData">重新加载</el-button>
        </div>
      </el-alert>

      <el-table ref="tableRef" :data="rows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange">
<OrderedTableColumns settings-key="resource-requests">
        <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
        <el-table-column type="index" label="序号" :width="PROJECT_LIST_COLUMN_WIDTHS.index" align="center" fixed="left" :index="rowIndex" />
        <el-table-column
          v-for="column in visibleColumns"
          :key="column.key"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :show-overflow-tooltip="column.tooltip !== false"
        >
          <template #header>
            <ConfiguredColumnHeaderFilter
              v-if="headerFilterDefinition(column.key)"
              :definition="headerFilterDefinition(column.key)"
              :model-value="filterModel[headerFilterDefinition(column.key).key]"
              @update:model-value="updateConfiguredFilter(headerFilterDefinition(column.key).key, $event)"
              @text-input="onConfiguredText(headerFilterDefinition(column.key), $event)"
              @change="search"
              @enter="search"
              @clear="search"
            />
            <span v-else>{{ column.label }}</span>
          </template>
          <template #default="{ row }">
            <ResourceRequestDetailPopover
              v-if="column.key === 'requestNo'"
              :request="detailOf(row)"
              :model-value="activeRequestDetailId === row.id"
              @update:model-value="value => activeRequestDetailId = value ? row.id : ''"
              @show="loadDetail(row)"
              @hide="cancelInlineDetailEdit"
            >
              <template #default="{ openProject, hasProject }">
              <div class="detail" v-loading="detailLoading === row.id">
                <ResourceRequestDetailContent :request="detailOf(row)" :project-types="projectTypesText(detailOf(row))" :project-status="projectStatusText(detailOf(row))" :owner-label="ownerName(detailOf(row))">
                  <template #project><el-button v-if="hasProject" link type="primary" class="associated-project-link" title="点击查看项目详情" @click.stop="openProject($event.currentTarget)">{{ detailOf(row).currentProjectName || detailOf(row).sourceProjectNameSnapshot || '-' }}</el-button><span v-else>{{ detailOf(row).currentProjectName || detailOf(row).sourceProjectNameSnapshot || '-' }}</span></template>
                  <template #items><LanguageItemsPopover :items="detailOf(row).items || []" :languages="languages" mode="all" :request-detail="detailOf(row).requestDetail" :always-expanded="true" :editable="canWrite && !deleteMode" :save-item="(item, value) => saveRequestItemTextField(row, item, value)" :on-conflict="() => loadDetail(row, true)" /></template>
                </ResourceRequestDetailContent>
              </div>
              </template>
            </ResourceRequestDetailPopover>
            <span v-else-if="column.key === 'sourceType'">{{ sourceLabels[row.sourceType] || '-' }}</span>
            <el-tag v-else-if="column.key === 'demandStatus'" :type="demandStatusType(row.demandStatus)" size="small">{{ demandStatusLabels[row.demandStatus] || '-' }}</el-tag>
            <span v-else-if="column.key === 'projectType'">{{ projectTypesText(row) }}</span>
            <el-tag v-else-if="column.key === 'projectStatus'" size="small" type="info">{{ projectStatusText(row) }}</el-tag>
            <span v-else-if="column.key === 'orderNo'">{{ row.currentOrderNo || row.sourceOrderNoSnapshot || '-' }}</span>
            <span v-else-if="column.key === 'projectName'">{{ row.currentProjectName || row.sourceProjectNameSnapshot || '-' }}</span>
            <span v-else-if="column.key === 'clientCode'">{{ row.clientCodeSnapshot || '-' }}</span>
            <span v-else-if="column.key === 'clientShortName'">{{ row.clientShortNameSnapshot || '-' }}</span>
            <LanguageItemsPopover v-else-if="column.key === 'languages'" :items="row.items || []" :languages="languages" mode="language" />
            <LanguageItemsPopover v-else-if="column.key === 'requiredCount'" :items="row.items || []" :languages="languages" mode="count" />
            <LanguageItemsPopover v-else-if="column.key === 'requestDetail'" :items="row.items || []" :languages="languages" mode="detail" :request-detail="row.requestDetail" />
            <el-tag v-else-if="column.key === 'priority'" :type="priorityType(row.priority)" size="small">{{ priorityLabels[row.priority] || '-' }}</el-tag>
            <span v-else-if="column.key === 'ownerName'">{{ ownerName(row) }}</span>
            <el-progress v-else-if="column.key === 'progress'" :percentage="row.progressPercent" :stroke-width="10" />
            <el-tag v-else-if="column.key === 'requestStatus'" :type="statusType(row.requestStatus)" size="small">{{ statusLabels[row.requestStatus] || '-' }}</el-tag>
            <span v-else-if="column.key === 'requestedAt'">{{ formatDate(row.requestedAt) }}</span>
            <span v-else-if="column.key === 'arrangedPlatforms'">{{ [...new Set((row.arrangements || []).map(item => item.platformName))].join('、') || '暂未安排' }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="(canWrite || (arrangementMode && arrangementOptions.can_delegate)) && !deleteMode" label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <PrimaryEditButton v-if="canWrite" @click="openEditor(row)" />
            <el-button v-if="!arrangementMode" link type="primary" :disabled="row.demandStatus === 'paused'" @click="openProgress(row)">更新进度</el-button>
            <el-button v-else-if="arrangementOptions.can_delegate" link type="primary" :disabled="row.demandStatus !== 'confirmed' || row.requestStatus === 'cancelled' || arranging" @click="openRowArrangement(row)">每日安排</el-button>
          </template>
        </el-table-column>
      </OrderedTableColumns>
</el-table>
      <el-pagination class="pagination" v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :page-sizes="arrangementMode ? [5, 10, 20, 50] : [10, 20, 50, 100]" :total="pagination.total" layout="total, sizes, prev, pager, next" @size-change="pageSizeChanged" @current-change="pageChanged" />
    </component>

    <DraggableFormDialog v-model="dialogVisible" :title="form.id ? '编辑资源需求' : '新增资源需求'" width="min(960px, calc(100vw - 32px))" top="5vh" class="resource-dialog" append-to-body :show-close="!editorBusy" :before-close="beforeEditorClose" @closed="onEditorClosed">
      <template #header>
        <DialogFieldSearchHeader
          ref="fieldSearchRef"
          v-model="fieldSearchKeyword"
          :title="form.id ? '编辑资源需求' : '新增资源需求'"
          subtitle="搜索并快速定位资源需求字段"
          :fetch-suggestions="fetchFieldSuggestions"
          placeholder="搜索资源需求字段，如请求类别"
          @select="locateDialogField"
          @clear="clearFieldSearch"
        />
      </template>
      <div ref="editorBodyRef" :inert="editorBusy || undefined">
        <AppForm ref="formRef" :model="form" :rules="formRules" :disabled="editorBusy" :validate-on-rule-change="false" label-width="110px">
        <div class="lifecycle-bar">
          <div>
            <span class="lifecycle-label">当前状态</span>
            <el-tag :type="demandStatusType(form.demandStatus)">{{ editorDemandStatusText }}</el-tag>
          </div>
          <span v-if="autoSaveText" class="autosave-state" :class="`is-${autoSaveState}`">{{ autoSaveText }}</span>
        </div>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12"><el-form-item label="项目类型" prop="sourceType"><el-select v-model="form.sourceType" style="width: 100%" @change="sourceChanged"><el-option v-for="(label, value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="12"><el-form-item label="请求类别" prop="requestCategory"><el-select v-model="form.requestCategory" style="width: 100%"><el-option v-for="item in availableCategories" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item v-if="form.sourceType !== 'other'" label="来源项目" prop="sourceProjectId">
          <div v-if="form.sourceType==='annotation' && form.sourceProjectId" class="source-project-reference">
            <ReadonlyField :model-value="sourceInfo.orderNo" source="auto" />
            <AnnotationProjectDetailPopover :key="form.sourceProjectId" :project-id="form.sourceProjectId" :summary="sourceInfo" placement="bottom" :teleported="false">
              <template #reference><el-button link type="primary" class="source-project-name" title="点击查看项目详情" @click.stop>{{ sourceInfo.projectName || '查看项目详情' }}</el-button></template>
            </AnnotationProjectDetailPopover>
            <AnnotationConversationEntry :key="form.sourceProjectId" :project-id="form.sourceProjectId" />
          </div>
          <el-select v-else v-model="form.sourceProjectId" filterable remote :remote-method="searchSourceProjects" style="width: 100%" :loading="sourceOptionsLoading || prefillLoading" @change="sourceProjectChanged">
            <el-option v-for="item in availableProjects" :key="item.id" :label="`${item.orderNo || ''} ${item.projectName || '未命名'}`.trim()" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="其他类型" prop="otherProjectTypes">
          <el-select v-model="form.otherProjectTypes" multiple filterable allow-create default-first-option style="width: 100%" placeholder="输入其他类型后按回车，可添加多个">
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>



        <el-row :gutter="16">
          <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.priority" style="width: 100%"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="12"><el-form-item :label="form.sourceType==='annotation' ? '项目经理' : '负责人'"><ReadonlyField v-if="form.sourceType==='annotation'" :model-value="projectManagers.map(p=>p.name).join('、') || '尚未登记项目经理'" source="auto" /><el-select v-else v-model="form.ownerId" clearable filterable style="width: 100%"><el-option v-for="user in users" :key="user.id" :label="userName(user)" :value="user.id" /></el-select></el-form-item></el-col>
        </el-row>

        <section class="items">
          <div class="section-title">
            <div><strong>需求语种、人数及详情</strong><div class="section-hint">已自动获取来源项目内容；方言或未收录语种可直接输入后创建。</div></div>
            <el-button type="primary" plain @click="addItem">添加明细</el-button>
          </div>
          <el-form-item label="总体需求" prop="requestDetail"><el-input v-model="form.requestDetail" type="textarea" :rows="5" placeholder="填写整个需求的总体说明，支持粘贴截图" /></el-form-item>
          <el-alert v-if="form.partialRequested" title="已删除语种明细，本次将按“部分语种”编号发送，可继续发起下一批需求。" type="info" :closable="false" />
          <el-empty v-if="!form.items.length" description="暂无结构化明细" :image-size="64" />
          <template v-for="(group, groupIndex) in [form.items.slice(0, 1), form.items.slice(1)]" :key="`${editorLayoutKey}-${groupIndex}`">
            <component :is="groupIndex === 0 ? 'div' : 'details'" v-if="group.length" :class="{'other-request-items': groupIndex > 0}">
              <summary v-if="groupIndex > 0">其他明细（{{ group.length }}项，点击展开）</summary>
          <details v-for="(item, localIndex) in group" :key="item.id || localIndex" class="item-card">
            <summary>{{ `明细 ${localIndex+groupIndex+1} · ${languageText([item], languages).join('、')}` }}<el-button link type="danger" :disabled="editorBusy" :aria-label="`删除明细${localIndex + groupIndex + 1}`" @click.stop.prevent="removeRequestItem(localIndex + groupIndex)">删除</el-button></summary>
            <div class="item-title"><span>明细 {{ localIndex + groupIndex + 1 }}</span><el-button link type="danger" @click="removeRequestItem(localIndex + groupIndex)">删除</el-button></div>
            <div class="request-language-row">
              <div class="request-language-chain">
                <template v-for="(_languageId, languageIndex) in item.languageIds" :key="languageIndex">
                  <span v-if="languageIndex" class="request-language-arrow">↔</span>
                  <div class="request-language-node">
                    <el-select v-model="item.languageIds[languageIndex]" clearable filterable allow-create default-first-option :placeholder="languageIndex ? `语种 ${languageIndex + 1}` : '需求语种/源语种'">
                      <el-option v-for="language in languages" :key="language.id" :label="languageOptionLabel(language)" :value="language.id" />
                    </el-select>
                    <el-button v-if="languageIndex >= 2" class="request-language-remove" link type="danger" :icon="CircleClose" :aria-label="`移除语种 ${languageIndex + 1}`" @click="removeItemLanguage(item, languageIndex)" />
                  </div>
                </template>
                <el-button link type="primary" :icon="Plus" :disabled="item.languageIds.length >= 5" @click="item.languageIds.push(null)">{{ item.languageIds.length >= 5 ? '最多 5 个' : '增加语种' }}</el-button>
              </div>
              <el-input-number v-model="item.requiredCount" :min="1" placeholder="需求人数（可空）" class="request-language-count" />
            </div>
            <el-input v-model="item.requirementDetail" type="textarea" :rows="2" placeholder="该语种具体要求；完整需求默认放在第一条明细" style="margin-top: 10px" />
          </details>
            </component>
          </template>
        </section>
        <ResourceRequestVersions v-model="form.requestContent.versions" editable :disabled="editorBusy" />
        <el-button link :loading="sendHistory.loading.value" @click="sendHistory.refresh">刷新发送及执行记录</el-button>
        <template v-if="form.sourceType==='annotation'">
          <ResourceRequestDispatchSection v-model="form.requestContent.dispatchNotes.circle" :request-id="form.id" :cancel-disabled="editorBusy || !!sendHistory.error.value" :active="dialogVisible" kind="circle" label="发圈需求" :prepare="prepareDispatch" :disabled="editorBusy || !!sendHistory.error.value" :records="sendHistory.records.value.circle" :history-loading="sendHistory.loading.value" @sent="sendHistory.refresh" @busy="dispatchBusy=$event" />
          <ResourceRequestDispatchSection v-model="form.requestContent.dispatchNotes.post" :request-id="form.id" :cancel-disabled="editorBusy || !!sendHistory.error.value" :active="dialogVisible" kind="post" label="发帖需求" :prepare="prepareDispatch" :disabled="editorBusy || !!sendHistory.error.value" :records="sendHistory.records.value.post" :history-loading="sendHistory.loading.value" @sent="sendHistory.refresh" @busy="dispatchBusy=$event" />
        </template>
        <el-alert v-if="sendHistory.error.value" :title="sendHistory.error.value" type="error" :closable="false"><el-button link @click="sendHistory.refresh">重新加载发送记录</el-button></el-alert>
        <ResourceRequestDispatchSection v-model="form.requestContent.dispatchNotes.development" :request-id="form.id" :cancel-disabled="editorBusy || !!sendHistory.error.value" :active="dialogVisible" kind="development" label="资源开拓 · 需求管理" @cancel="cancelDemand" :prepare="prepareDispatch" :disabled="editorBusy || !canSendDemand(form) || !!sendHistory.error.value" :records="sendHistory.records.value.development" :history-loading="sendHistory.loading.value" @sent="managementSent" @busy="dispatchBusy=$event" />
        </AppForm>
      </div>
      <template #footer>
        <div class="editor-footer">
          <div class="editor-footer-lifecycle">
            <el-button v-if="['confirmed', 'paused'].includes(form.demandStatus)" type="danger" plain :loading="cancelling" :disabled="editorBusy" @click="cancelDemand">取消需求</el-button>
            <el-button v-if="canPauseDemand(form)" type="warning" plain :disabled="editorBusy" @click="openLifecycleDialog(false)">暂停需求</el-button>
            <el-button v-if="form.demandStatus === 'paused'" type="primary" plain :disabled="editorBusy" @click="openLifecycleDialog(true)">恢复需求</el-button>
          </div>
          <div class="editor-footer-actions">
            <el-button :disabled="editorBusy" @click="requestEditorClose">关闭</el-button>
            <el-button :loading="saving" :disabled="editorBusy" @click="saveDraftManually">保存</el-button>
            <el-button v-if="canArrangeDemand" type="primary" :loading="arranging" :disabled="editorBusy" @click="openDailyArrangement">发到每日安排</el-button>
          </div>
        </div>
      </template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="lifecycleDialog" :title="resuming ? '恢复需求' : '暂停需求'" width="min(520px, calc(100vw - 32px))" top="8vh" class="resource-lifecycle-dialog" append-to-body :show-close="!lifecycleSaving" :before-close="beforeLifecycleClose" @closed="scheduleAutoSave">
      <p class="lifecycle-hint">{{ resuming ? '恢复后可继续资源开拓并新增每日安排，原进度及已有安排将保留。' : '暂停后将停止新增每日安排，已有安排保留并标记暂停，可随时恢复。' }}</p>
      <AppForm ref="lifecycleFormRef" :model="lifecycleForm" :rules="lifecycleRules" :disabled="lifecycleSaving" label-position="top">
        <el-form-item v-if="!resuming" label="暂停原因（选填）" prop="reason">
          <el-input v-model="lifecycleForm.reason" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="例如：等待客户反馈或项目计划调整" />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button :disabled="lifecycleSaving" @click="lifecycleDialog = false">返回</el-button>
        <el-button :type="resuming ? 'primary' : 'warning'" :loading="lifecycleSaving" @click="submitLifecycleChange">{{ resuming ? '确认恢复' : '确认暂停' }}</el-button>
      </template>
    </DraggableFormDialog>

    <RequestArrangementDialog ref="arrangementRef" :options="arrangementOptions" @visibility-change="arrangementVisible = $event" @saved="arrangementSaved" />

    <DraggableFormDialog v-model="progressDialog" title="更新资源开拓进度" width="min(520px, calc(100vw - 32px))">
      <AppForm label-width="90px"><el-form-item label="完成比例"><el-slider v-model="progressForm.progressPercent" show-input /></el-form-item><el-form-item label="进度说明"><el-input v-model="progressForm.progressNote" type="textarea" :rows="3" /></el-form-item></AppForm>
      <template #footer><el-button @click="progressDialog = false">取消</el-button><el-button type="primary" @click="saveProgress">保存进度</el-button></template>
    </DraggableFormDialog>

  </div>
</template>

<script setup>
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import AnnotationConversationEntry from '@/components/chat/AnnotationConversationEntry.vue'
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElCard, ElMessage, ElMessageBox, ElPopover, ElTable, ElTableColumn } from 'element-plus'
// 手动导入及 h() 渲染的组件不会自动补齐样式，必须显式声明依赖。
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/card/style/css'
import 'element-plus/es/components/popover/style/css'
import 'element-plus/es/components/table/style/css'
import 'element-plus/es/components/table-column/style/css'
import { CircleClose, Plus } from '@element-plus/icons-vue'
import * as api from '@/api/resourceRequests'
import { developmentApi } from '@/api/resourceDevelopment'
import { arrangementTomorrow } from '@/utils/resourceArrangements'
import RequestArrangementDialog from './components/RequestArrangementDialog.vue'
import ResourceRequestDetailPopover from './components/ResourceRequestDetailPopover.vue'
import ResourceRequestDetailContent from './components/ResourceRequestDetailContent.vue'
import { projectTypeLabels } from '@/utils/resourceRequestProjectTypes'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'
import { getUserOptions } from '@/api/users'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import InlineTextField from '@/components/common/InlineTextField.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CompactFilterGrid from '@/components/common/CompactFilterGrid.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import { useResourceNotesDock } from '@/composables/useResourceNotesDock'
import { useTableColumns } from '@/composables/useTableColumns'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { useFormDraft } from '@/composables/useFormDraft'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import ResourceRequestVersions from './components/ResourceRequestVersions.vue'
import { useResourceRequestSendHistory } from '@/composables/useResourceRequestSendHistory'
import AnnotationProjectDetailPopover from '@/components/annotation/AnnotationProjectDetailPopover.vue'
const editorLayoutKey = ref(0)
import { mergeTaskVersions } from '@/utils/resourceRequestVersions'
import ResourceRequestDispatchSection from './components/ResourceRequestDispatchSection.vue'
const projectManagers=ref([]),collapseLanguages=ref(false),dispatchBusy=ref(false)
const canSendDemand=row=>baseCanSendDemand(row)||row.demandStatus==='confirmed'||Boolean(row.partialRequested && row.demandStatus==='confirmed' && !row.partialSequence)
function removeRequestItem(index){if(collapseLanguages.value)form.partialRequested=true;form.items.splice(index,1)}
function removeItemLanguage(item,index){if(collapseLanguages.value)form.partialRequested=true;item.languageIds.splice(index,1)}
async function prepareDispatch(){await formRef.value.validate();return form.id && editorRevision===savedRevision ? {...form} : persistDraft()}

import { hasPermission } from '@/utils/permission'
import { formatBusinessDateTimeMinute as formatDate, businessDateTimeInputValue } from '@/utils/dateTime'
import { canPauseDemand, canSendDemand as baseCanSendDemand, demandStatusLabels, demandStatusText, demandStatusType } from '@/utils/resourceRequestLifecycle'
import { countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '@/utils/listFieldFilters'
import { PROJECT_LIST_COLUMN_WIDTHS } from '@/constants/projectListTable'
import { getCachedOptions } from '@/utils/optionCache'

const props = defineProps({ embedded: { type: Boolean, default: false }, arrangementMode: Boolean, editorOnly: Boolean, sourceRequest: {type:Object,default:null} })
const emit = defineEmits(['arrangement-saved', 'requests-changed', 'editor-closed'])
const activeRequestDetailId = ref('')

const languageText = (items, languages) => {
  const label = (id) => languages.find((item) => item.id === id)?.label || '-'
  return items.map((item) => {
    const ids = item.languageIds?.length ? item.languageIds : [item.sourceLanguageId, item.targetLanguageId].filter(Boolean)
    const labels = item.languageLabels?.length === ids.length ? item.languageLabels : ids.map(label)
    return labels.join(ids.length > 2 ? ' ↔ ' : ' → ') || '-'
  })
}

const LanguageItemsPopover = defineComponent({
  props: { items: { type: Array, default: () => [] }, languages: { type: Array, default: () => [] }, mode: { type: String, default: 'all' }, requestDetail: { type: String, default: '' }, alwaysExpanded: Boolean, editable: Boolean, saveItem: { type: Function, default: null }, onConflict: { type: Function, default: null } },
  setup(props) {
    const rows = computed(() => props.items.map((item, index) => ({ ...item, sequence: index + 1, language: languageText([item], props.languages)[0] })))
    const summary = computed(() => {
      if (props.mode === 'language') return languageText(props.items, props.languages).join('、') || '-'
      if (props.mode === 'count') return props.items.map((item, index) => item.requiredCount ? `${languageText([item], props.languages)[0]} ${item.requiredCount}人` : (index === 0 ? '-' : '')).filter(Boolean).join('、') || '-'
      if (props.mode === 'detail') return props.requestDetail || props.items.find((item) => item.requirementDetail)?.requirementDetail || '-'
      return '-'
    })
    const table = () => h(ElTable, { data: rows.value, border: true, size: 'small', maxHeight: 360 }, () => [
      h(ElTableColumn, { prop: 'sequence', label: '序号', width: 48 }),
      h(ElTableColumn, { prop: 'language', label: '需求语种', minWidth: 170 }),
      h(ElTableColumn, { label: '需求人数', width: 90 }, { default: ({ row }) => row.requiredCount ? `${row.requiredCount} 人` : '-' }),
      h(ElTableColumn, { label: '具体要求', minWidth: 220 }, { default: ({ row }) => h(InlineTextField, {
        modelValue: row.requirementDetail,
        editable: props.editable,
        label: `第${row.sequence}条具体要求`,
        multiline: true,
        saveField: (value) => props.saveItem?.(row, value),
        onConflict: () => props.onConflict?.(),
      }) }),
    ])
    return () => {
      if (props.alwaysExpanded) return props.items.length ? table() : h('span', '-')
      if (props.items.length <= 1) return h('span', { class: 'cell-summary' }, summary.value)
      return h(ElPopover, { trigger: 'click', placement: 'left', width: 680, popperClass: 'resource-items-popover' }, { reference: () => h(ElButton, { link: true, type: 'primary' }, () => summary.value), default: table })
    }
  },
})

const route = useRoute()
const router = useRouter()
const rows = ref([])
const users = ref([])
const languages = ref([])
const projects = reactive({ annotation: [], recruitment: [], interpretation: [], translation: [] })
const sourceOptionsLoading = ref(false)
const loading = ref(false)
const listError = ref('')
const prefillLoading = ref(false)
const advancedVisible = ref(false)
const dialogVisible = ref(false)
const progressDialog = ref(false)
const { openNotes } = useResourceNotesDock()
const saving = ref(false)
const sending = ref(false)
const cancelling = ref(false)
const lifecycleDialog = ref(false)
const lifecycleSaving = ref(false)
const resuming = ref(false)
const lifecycleFormRef = ref(null)
const lifecycleForm = reactive({ reason: '' })
const lifecycleRules = { reason: [{ max: 500, message: '暂停原因不能超过 500 字', trigger: 'blur' }] }
const arranging = ref(false)
const arrangementVisible = ref(false)
const arrangementRef = ref(null)
const arrangementOptions = reactive({ options: [], arrangement_platforms: [], can_delegate: false })
const editorBusy = computed(() => dispatchBusy.value || saving.value || sending.value || cancelling.value || arranging.value || arrangementVisible.value || lifecycleDialog.value || lifecycleSaving.value)
const autoSaveState = ref('idle')
const lastAutoSavedAt = ref('')
let submitLocked = false
const detailLoading = ref('')
const detailCache = reactive({})
const showRequestDetail = ref(false)
const formRef = ref(null)
const editorBodyRef = ref(null)
const {
  fieldSearchRef,
  fieldSearchKeyword,
  fetchFieldSuggestions,
  locateDialogField,
  clearFieldSearch,
} = useDialogFieldSearch(editorBodyRef)
const pagination = reactive({ page: 1, limit: props.arrangementMode ? 5 : 10, total: 0 })
const tableRef = ref(null)
const canWrite = hasPermission('projects:write')
const searchForm = reactive({ keyword: '' })
const form = reactive({})
const sendHistory=useResourceRequestSendHistory(()=>form.id)
const canArrangeDemand = computed(() => canWrite && arrangementOptions.can_delegate && form.id && form.demandStatus === 'confirmed' && form.requestStatus !== 'cancelled')
const sourceInfo = reactive({ projectTypes: [], orderNo: '', projectName: '', projectStatus: '', clientCode: '', clientShortName: '' })
const progressForm = reactive({ id: '', progressPercent: 0, progressNote: '' })

const sourceLabels = { annotation: '标注', recruitment: '招聘', interpretation: '口译', translation: '笔译', other: '其他' }
const categoryLabels = { annotation_trial: '标注试标', annotation_formal: '标注正式', recruitment: '招聘', interpretation: '口译', translation: '笔译', other: '其他' }
const statusLabels = { draft: '草稿', submitted: '已提交', in_progress: '进行中', fulfilled: '已完成', cancelled: '已取消' }
const priorityLabels = { high: '高', medium: '中', low: '低' }
const projectStatusLabels = {
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果', resource_sourcing: '资源开拓', resource_sourcing_cancelled: '取消资源开拓', assessment_preparation:'准备考核',assessment_in_progress:'考核中',assessment_completed:'考核结束',trial_preparation: '试标准备', trial_in_progress: '试标中', trial_submitted: '试标已提交', trial_passed: '试标通过', trial_failed: '试标未通过', trial_partially_passed: '部分试标通过', project_in_progress: '项目进行中', sent_to_client: '已发客户', client_feedback: '客户反馈', partially_cancelled: '已部分取消', actively_abandoned: '主动放弃',
  pending_setup: '待启动', sourcing: '寻访中', recommending: '推荐中', interviewing: '面试中', offer_negotiation: 'Offer协商中', pending_onboard: '待入职', probation: '试用期', full_time_dispatch: '全职外派', cancelled: '项目取消', closed: '已关闭',
  initial_follow_up: '初步跟进中', deal_pending_execution: '已成交待执行', in_progress: '进行中', ended: '已结束', settled: '已结款', active: '进行中', completed: '已完成', cancelled: '已取消',
  pending_confirmation: '待确认', confirmed: '已确认', organized: '已整理', translator_assigned: '已排译员', sent_to_translator: '已发译员', translator_returned: '译员发回', special_checked: '已专检', typeset: '已排版', special_checked_typeset: '已专检排版', reviewed: '已审核', feedback_sent_to_client: '反馈后发客户', paused: '已暂停',
}

const optionsOf = (map) => Object.entries(map).map(([value, label]) => ({ value, label }))
const filterFields = [
  { key: 'requestNo', label: '需求编号', type: 'text' },
  { key: 'demandStatus', label: '需求状态', type: 'select', options: () => optionsOf(demandStatusLabels) },
  { key: 'sourceType', label: '来源', type: 'select', options: () => optionsOf(sourceLabels) },
  { key: 'requestCategory', label: '请求类别', type: 'select', options: () => optionsOf(categoryLabels) },
  { key: 'projectType', label: '项目类型', type: 'select', options: () => optionsOf(projectTypeLabels) },
  { key: 'projectStatus', label: '项目状态', type: 'select', options: () => optionsOf(projectStatusLabels) },
  { key: 'orderNo', label: '需求项目订单号', type: 'text' },
  { key: 'projectName', label: '需求项目', type: 'text' },
  { key: 'clientCode', label: '客户编号', type: 'text' },
  { key: 'clientShortName', label: '客户简称', type: 'text' },
  { key: 'ownerId', apiKey: 'owner_id', label: '负责人', type: 'select', options: () => users.value.map((user) => ({ value: user.id, label: userName(user) })) },
  { key: 'languages', label: '需求语种', type: 'select', options: () => languages.value.map((item) => ({ value: item.id, label: item.label })) },
  { key: 'requiredCount', label: '需求人数', type: 'number-range', min: 0, wide: true },
  { key: 'requestDetail', label: '需求详情', type: 'text', wide: true },
  { key: 'priority', label: '优先级', type: 'select', options: () => optionsOf(priorityLabels) },
  { key: 'progress', apiKey: 'progress_percent', label: '进度百分比', type: 'number-range', min: 0, max: 100, wide: true },
  { key: 'requestStatus', label: '请求状态', type: 'select', options: () => optionsOf(statusLabels) },
  { key: 'requestedAt', label: '发起时间', type: 'date-range', wide: true },
]
const filterModel = reactive(createFilterModel(filterFields))
const advancedFilterFields = filterFields.filter((item) => !['requestNo', 'requestStatus'].includes(item.key))

const tableColumns = [
  { key: 'requestNo', label: '需求编号', width: PROJECT_LIST_COLUMN_WIDTHS.orderNo },
  { key: 'demandStatus', label: '需求状态', width: 110 },
  { key: 'projectType', label: '项目类型', minWidth: 120 },
  { key: 'sourceType', label: '来源', width: 82 },
  { key: 'projectStatus', label: '项目状态', width: 110 },
  { key: 'orderNo', label: '需求项目订单号', width: 145 },
  { key: 'projectName', label: '需求项目', minWidth: 190 },
  { key: 'clientCode', label: '客户编号', width: 120 },
  { key: 'clientShortName', label: '客户简称', width: 110 },
  { key: 'ownerName', label: '负责人', width: 110 },
  { key: 'languages', label: '需求语种', minWidth: 170 },
  { key: 'requiredCount', label: '需求人数', minWidth: 135 },
  { key: 'requestDetail', label: '需求详情', minWidth: 180 },
  { key: 'priority', label: '优先级', width: 78 },
  { key: 'progress', label: '进度', width: 145, tooltip: false },
  { key: 'requestStatus', label: '请求状态', width: 100 },
  { key: 'requestedAt', label: '发起时间', width: 165 },
]
if (props.arrangementMode) tableColumns.push({ key: 'arrangedPlatforms', label: '已安排平台', minWidth: 160 })
const legacyDefaultColumnKeys = ['projectType', 'projectStatus', 'projectName', 'clientShortName', 'languages', 'requiredCount', 'requestDetail']
const defaultColumnKeys = ['requestNo', 'demandStatus', ...legacyDefaultColumnKeys, ...(props.arrangementMode ? ['arrangedPlatforms'] : [])]
const { selectedKeys: selectedColumnKeys, reset: resetColumns } = useTableColumns(
  props.arrangementMode ? 'daily-arrangement-requests' : 'resource-requests',
  tableColumns,
  defaultColumnKeys,
  { legacyDefaultKeys: [legacyDefaultColumnKeys, ['requestNo', ...legacyDefaultColumnKeys]] }
)
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination,deleteRow:(row)=>api.deleteResourceRequest(row.id),getLabel:(row)=>row.requestNo||row.currentProjectName||row.id,reload:async()=>{await fetchData(); emit('requests-changed')},onDeleted:(row)=>{delete detailCache[row.id]},entityName:'资源需求'})
const visibleColumns = computed(() => tableColumns.filter((column) => selectedColumnKeys.value.includes(column.key)))
const advancedCount = computed(() => countActiveFilters(filterModel, advancedFilterFields))
const resourceRequestHeaderFieldMap = { ownerName: 'ownerId' }
const headerFilterDefinition = (key) => {
  const fieldKey = resourceRequestHeaderFieldMap[key] || key
  return filterFields.find((item) => item.key === fieldKey) || null
}
const availableProjects = computed(() => projects[form.sourceType] || [])
const availableCategories = computed(() => form.sourceType === 'annotation' ? [{ value: 'annotation_trial', label: '标注试标' }, { value: 'annotation_formal', label: '标注正式' }] : [{ value: form.sourceType, label: sourceLabels[form.sourceType] }])
const formRules = computed(() => ({
  sourceType: [{ required: true, message: '请选择项目类型', trigger: 'change' }],
  requestCategory: [{ required: true, message: '请选择请求类别', trigger: 'change' }],
  sourceProjectId: [{ required: form.sourceType !== 'other', message: '请选择来源项目', trigger: 'change' }],
  otherProjectTypes: [{ type: 'array', required: form.sourceType === 'other', min: 1, message: '请至少填写一个其他类型', trigger: 'change' }],
}))

let timer
let controller
let requestId = 0
let sourceOptionController = null
let sourceOptionTimer = null
const emptyForm = () => ({ id: '', sourceType: 'annotation', requestCategory: 'annotation_trial', sourceProjectId: '', otherProjectTypes: [], requestDetail: '', priority: 'medium', requestStatus: 'draft', demandStatus: 'draft', ownerId: '', requestContent:{versions:[{name:'发帖',content:''},{name:'询问',content:''}],dispatchNotes:{circle:'',post:'',development:''}}, partialRequested:false, partialSequence:0, items: [] })
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({ namespace: 'resource-request', form, createDefault: emptyForm, formRef })
const resetSourceInfo = () => Object.assign(sourceInfo, { projectTypes: [], orderNo: '', projectName: '', projectStatus: '', clientCode: '', clientShortName: '' })
const params = () => ({ keyword: searchForm.keyword.trim() || undefined, field_filters: serializeFieldFilters(filterModel, filterFields) })
const fetchData = async () => {
  if (props.editorOnly) return
  controller?.abort()
  controller = new AbortController()
  const current = ++requestId
  loading.value = true
  listError.value = ''
  try {
    const filters = params()
    const page = await api.getResourceRequestPage(
      { skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit, ...filters, ...(props.arrangementMode ? { include_arrangements: true } : {}) },
      { signal: controller.signal },
    )
    if (current !== requestId) return
    rows.value = page?.items || []
    pagination.total = page?.total || 0
    const lastPage = Math.max(1, Math.ceil(pagination.total / pagination.limit))
    if (pagination.page > lastPage) { pagination.page = lastPage; return fetchData() }
  } catch (error) {
    if (error.code !== 'ERR_CANCELED' && current === requestId) {
      listError.value = error.detail || '网络异常，资源需求列表未刷新，请检查网络后重试'
      ElMessage.error(listError.value)
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}
const search = () => { exitDeleteMode(); clearTimeout(timer); pagination.page = 1; fetchData() }
const pageChanged = () => { exitDeleteMode(); fetchData() }
const pageSizeChanged = () => { exitDeleteMode(); pagination.page = 1; fetchData() }
const onKeyword = (value) => { clearTimeout(timer); controller?.abort(); requestId++; loading.value = false; if (!value) return search(); timer = setTimeout(search, 400) }
const updateConfiguredFilter = (key, value) => { filterModel[key] = value }
const onConfiguredText = (_definition, value) => onKeyword(value)
const reset = () => { searchForm.keyword = ''; resetFilterModel(filterModel, filterFields); search() }
const clearAdvanced = () => { resetFilterModel(filterModel, advancedFilterFields); search() }
const rowIndex = (index) => (pagination.page - 1) * pagination.limit + index + 1
const userName = (user) => user.full_name || user.fullName || user.username
const ownerName = (row) => {
  if (row.ownerName || row.owner_name) return row.ownerName || row.owner_name
  const ownerId = row.ownerId || row.owner_id
  if (!ownerId) return '-'
  const user = users.value.find((item) => item.id === ownerId)
  return user ? userName(user) : '-'
}
const languageOptionLabel = (language) => language.isCustom ? `${language.label}（自定义）` : language.label
const priorityType = (value) => ({ high: 'danger', medium: 'warning', low: 'info' }[value])
const statusType = (value) => ({ draft: 'info', submitted: 'warning', in_progress: 'primary', fulfilled: 'success', cancelled: 'danger' }[value])
const editorDemandStatusText = computed(() => demandStatusText(form.demandStatus))
const autoSaveText = computed(() => {
  if (autoSaveState.value === 'saving') return '自动保存中…'
  if (autoSaveState.value === 'saved') return lastAutoSavedAt.value ? `已自动保存 ${lastAutoSavedAt.value}` : '已自动保存'
  if (autoSaveState.value === 'error') return '自动保存失败，请手动保存'
  return ''
})
const projectTypeLabel = (value) => projectTypeLabels[value] || value || '-'
const projectStatusLabel = (value) => projectStatusLabels[value] || value || '-'
const projectTypesText = (row) => row.sourceProjectTypesSnapshot?.length ? row.sourceProjectTypesSnapshot.map(projectTypeLabel).join('、') : (categoryLabels[row.requestCategory] || sourceLabels[row.sourceType] || '-')
const projectStatusText = (row) => projectStatusLabel(row.currentProjectStatus || row.sourceStatusSnapshot)
const detailOf = (row) => detailCache[row.id] || row
const cancelInlineDetailEdit = () => window.dispatchEvent(new CustomEvent('business-inline-text-edit', { detail: 'popover-hidden' }))
const saveRequestTextField = async (row, value) => {
  const current = detailOf(row)
  const updated = await api.updateResourceRequestTextField(row.id, 'requestDetail', value, current.updatedAt)
  detailCache[row.id] = updated
  Object.assign(row, updated)
  if (Object.values(params()).some(Boolean)) void fetchData()
  return updated
}
const saveRequestItemTextField = async (row, item, value) => {
  const current = detailOf(row)
  const updated = await api.updateResourceRequestItemTextField(row.id, item.id, 'requirementDetail', value, current.updatedAt)
  detailCache[row.id] = updated
  Object.assign(row, updated)
  if (Object.values(params()).some(Boolean)) void fetchData()
  return updated
}
const loadDetail = async (row, force = false) => {
  if (!force && detailCache[row.id]) return
  detailLoading.value = row.id
  try {
    detailCache[row.id] = await api.getResourceRequest(row.id)
  } catch (error) {
    ElMessage.error(error.detail || '加载资源需求详情失败')
  } finally {
    detailLoading.value = ''
  }
}

const loadSourceOptions = async (keyword = '') => {
  if (form.sourceType === 'other') return
  sourceOptionController?.abort()
  sourceOptionController = new AbortController()
  const currentController = sourceOptionController
  const sourceType = form.sourceType
  sourceOptionsLoading.value = true
  try {
    const normalizedKeyword = String(keyword || '').trim()
    projects[sourceType] = await getCachedOptions(
      `source-projects:${sourceType}:${normalizedKeyword.toLowerCase()}`,
      () => api.getResourceRequestSourceOptions(
        sourceType,
        { keyword: normalizedKeyword || undefined, limit: 50 },
        { signal: currentController.signal },
      ),
      { ttlMs: 30_000 },
    )
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED') ElMessage.error(error.detail || '来源项目加载失败')
  } finally {
    if (sourceOptionController === currentController) sourceOptionsLoading.value = false
  }
}
const searchSourceProjects = (keyword) => {
  clearTimeout(sourceOptionTimer)
  if (!String(keyword || '').trim()) return loadSourceOptions('')
  sourceOptionTimer = setTimeout(() => loadSourceOptions(keyword), 400)
}
const sourceChanged = () => { form.sourceProjectId = ''; form.otherProjectTypes = []; form.requestCategory = form.sourceType === 'annotation' ? 'annotation_trial' : form.sourceType; form.requestDetail = ''; form.items = []; showRequestDetail.value = false; resetSourceInfo(); void loadSourceOptions(); nextTick(() => formRef.value?.clearValidate()) }
let previousTaskCopy=''
const sourceProjectChanged = async (projectId) => {
  if (!projectId) return resetSourceInfo()
  prefillLoading.value = true
  try {
    const sourceType=form.sourceType
    const value = await api.getResourceRequestSourcePrefill(sourceType, projectId)
    if(form.sourceType!==sourceType || form.sourceProjectId!==projectId)return
    if(sourceType==='annotation'){
      const sourceVersions=value.requestContent?.versions || []
      form.requestContent.versions=mergeTaskVersions(form.requestContent.versions,sourceVersions,previousTaskCopy)
      previousTaskCopy=sourceVersions[0]?.content || ''
    }
    projectManagers.value=value.projectManagers||[];collapseLanguages.value=Boolean(value.collapseLanguages)
    if(form.sourceType==='annotation')form.ownerId=projectManagers.value[0]?.id||''
    form.requestCategory = value.requestCategory || form.requestCategory
    Object.assign(sourceInfo, { projectTypes: value.sourceProjectTypes || [], orderNo: value.orderNo || '', projectName: value.projectName || '', projectStatus: value.projectStatus || '', clientCode: value.clientCode || '', clientShortName: value.clientShortName || '' })
    const selectedProject = { id: projectId, orderNo: sourceInfo.orderNo, projectName: sourceInfo.projectName, projectStatus: sourceInfo.projectStatus, clientShortName: sourceInfo.clientShortName }
    projects[form.sourceType] = [selectedProject, ...availableProjects.value.filter(item => item.id !== projectId)]
    form.requestDetail = sourceType==='annotation' ? '' : (value.requestDetail || '')
    form.items = (value.items || []).map((item) => ({ id: null, languageIds: item.languageIds?.length ? [...item.languageIds] : [item.sourceLanguageId, item.targetLanguageId].filter(Boolean), requiredCount: item.requiredCount || null, requirementDetail: sourceType==='annotation' ? '' : (item.requirementDetail || '') }))
    showRequestDetail.value = Boolean(form.requestDetail)
  } catch (error) { ElMessage.error(error.detail || '自动获取项目需求信息失败') } finally { prefillLoading.value = false }
}
const openEditor = async (row = null, source = null) => {
  if (!row?.id) api.resetResourceRequestIdempotency()
  let value = row
  if (row?.id) value = await api.getResourceRequest(row.id)
  editorReady = false
  previousTaskCopy=''
  editorLayoutKey.value++
  Object.assign(form, emptyForm(), value || {})
  form.requestContent={versions:value?.requestContent?.versions?.length ? value.requestContent.versions : [{name:'发帖',content:''},{name:'询问',content:''}],dispatchNotes:{circle:'',post:'',development:'',...(value?.requestContent?.dispatchNotes || {})}}
  projectManagers.value=value?.projectManagers||[];collapseLanguages.value=Boolean(value?.collapseLanguages)
  resetSourceInfo()
  if (value) {
    form.sourceProjectId = value[`${value.sourceType}ProjectId`] || ''
    form.otherProjectTypes = value.sourceType === 'other' ? (value.otherSourceName || '').replaceAll('，', ',').split(',').map((item) => item.trim()).filter(Boolean) : []
    form.items = (value.items || []).map((item) => ({ ...item, languageIds: item.languageIds?.length ? [...item.languageIds] : [item.sourceLanguageId, item.targetLanguageId].filter(Boolean) }))
    Object.assign(sourceInfo, { projectTypes: value.sourceProjectTypesSnapshot || [], orderNo: value.currentOrderNo || value.sourceOrderNoSnapshot || '', projectName: value.currentProjectName || value.sourceProjectNameSnapshot || '', projectStatus: value.currentProjectStatus || value.sourceStatusSnapshot || '', clientCode: value.clientCodeSnapshot || '', clientShortName: value.clientShortNameSnapshot || '' })
  }
  if (source) {
    form.sourceType = source.sourceType
    form.requestCategory = source.requestCategory || (source.sourceType === 'annotation' ? 'annotation_trial' : source.sourceType)
    form.sourceProjectId = source.sourceProjectId
  }
  arrangementOptions.can_delegate = false
  await Promise.all([loadSourceOptions(), loadArrangementOptions().catch(error => {
    ElMessage.error(getLocalizedErrorMessage(error, '加载每日安排权限失败，请重新打开需求窗口重试'))
  })])
  showRequestDetail.value = Boolean(form.requestDetail)
  if (source?.sourceProjectId) await sourceProjectChanged(source.sourceProjectId)
  else if(value?.id && form.sourceType==='annotation' && form.sourceProjectId && form.requestContent.versions.some(v=>['发帖','询问'].includes(v.name.replace(/版$/,'')) && !String(v.content||'').trim())){
    try{const prefill=await api.getResourceRequestSourcePrefill('annotation',form.sourceProjectId);form.requestContent.versions=mergeTaskVersions(form.requestContent.versions,prefill.requestContent?.versions || [])}catch(e){ElMessage.error(e.detail || '具体任务自动复制失败，可重新打开窗口重试')}
  }
  if (form.sourceProjectId && !availableProjects.value.some((item) => item.id === form.sourceProjectId)) {
    projects[form.sourceType].unshift({ id: form.sourceProjectId, orderNo: sourceInfo.orderNo, projectName: sourceInfo.projectName, projectStatus: sourceInfo.projectStatus, clientShortName: sourceInfo.clientShortName })
  }
  dialogVisible.value = true
  await nextTick()
  const draftKey = value?.id
    ? `edit:${value.id}`
    : source?.sourceProjectId
      ? `create:${source.sourceType}:${source.sourceProjectId}`
      : 'create'
  await beginDraft(draftKey)
  // 恢复旧草稿后补齐空版本，避免旧草稿把刚复制的两版内容覆盖为空。
  if(form.sourceType==='annotation' && form.sourceProjectId && form.requestContent.versions.some(v=>['发帖','询问'].includes(v.name.replace(/版$/,'')) && !String(v.content||'').trim())){
    try{const prefill=await api.getResourceRequestSourcePrefill('annotation',form.sourceProjectId);form.requestContent.versions=mergeTaskVersions(form.requestContent.versions,prefill.requestContent?.versions || [])}catch(e){ElMessage.error(e.detail || '具体任务自动复制失败，请重新打开窗口重试')}
  }
  editorRevision = 0
  savedRevision = 0
  autoSaveState.value = 'idle'
  lastAutoSavedAt.value = ''
  editorReady = true
}
const resetEditor = () => { clearFieldSearch(); formRef.value?.clearValidate(); Object.assign(form, emptyForm()); resetSourceInfo(); showRequestDetail.value = false }
const onEditorClosed = () => { editorReady = false; clearTimeout(autoSaveTimer); pauseDraft(); resetEditor(); emit('editor-closed') }
const addItem = () => form.items.push({ id: null, languageIds: [null], requiredCount: null, requirementDetail: '' })

const ensureLanguageId = async (value) => {
  if (!value) return null
  if (languages.value.some((item) => item.id === value)) return value
  const label = String(value).trim()
  const existing = languages.value.find((item) => item.label.toLowerCase() === label.toLowerCase())
  if (existing) return existing.id
  const created = await createProjectLanguage(label)
  languages.value.push(created)
  return created.id
}
const normalizeItems = async () => {
  const meaningful = form.items.filter((item) => item.languageIds.some(Boolean) || item.requiredCount || item.requirementDetail?.trim())
  return Promise.all(meaningful.map(async (item) => ({
    id: item.id || null,
    languageIds: await Promise.all(item.languageIds.filter(Boolean).map(ensureLanguageId)),
    requiredCount: item.requiredCount || null,
    requirementDetail: item.requirementDetail?.trim() || null,
  })))
}
const payload = async () => {
  const data = { sourceType: form.sourceType, requestCategory: form.requestCategory, annotationProjectId: null, recruitmentProjectId: null, interpretationProjectId: null, translationProjectId: null, otherSourceName: form.sourceType === 'other' ? form.otherProjectTypes.map((item) => item.trim()).filter(Boolean).join(',') : null, requestDetail: form.requestDetail.trim(), requestContent:form.requestContent, partialRequested:form.partialRequested, priority: form.priority, requestStatus: form.requestStatus, ownerId: form.ownerId || null, items: await normalizeItems() }
  if (form.sourceType !== 'other') data[`${form.sourceType}ProjectId`] = form.sourceProjectId
  return data
}
let autoSaveTimer = null
let editorReady = false
let applyingSavedValue = false
let editorRevision = 0
let savedRevision = 0
let activePersistPromise = null

const canPersistDraft = () => form.sourceType === 'other'
  ? form.otherProjectTypes.some((item) => item?.trim())
  : Boolean(form.sourceProjectId)

const applySavedRequest = (saved) => {
  applyingSavedValue = true
  const sourceProjectId = form.sourceProjectId
  const otherProjectTypes = [...form.otherProjectTypes]
  const items = (saved.items || []).map((item) => ({ ...item, languageIds: item.languageIds?.length ? [...item.languageIds] : [item.sourceLanguageId, item.targetLanguageId].filter(Boolean) }))
  Object.assign(form, saved, { sourceProjectId, otherProjectTypes, items })
  nextTick(() => { applyingSavedValue = false })
}

const performPersistDraft = async ({ automatic = false } = {}) => {
  if (!canPersistDraft()) return null
  const revision = editorRevision
  if (automatic) autoSaveState.value = 'saving'
  const data = await payload()
  const newPartialBatch=form.demandStatus==='confirmed' && form.partialRequested && !form.partialSequence
  if(newPartialBatch)data.items=data.items.map(item=>({...item,id:null}))
  if (!form.id || newPartialBatch) data.requestStatus = 'draft'
  else data.expectedUpdatedAt = form.updatedAt
  const saved = form.id && !newPartialBatch ? await api.updateResourceRequest(form.id, data) : await api.createResourceRequest(data)
  if (editorRevision === revision) applySavedRequest(saved)
  else {
    applyingSavedValue = true
    Object.assign(form, {
      id: saved.id,
      requestNo: saved.requestNo,
      demandStatus: saved.demandStatus,
      requestStatus: saved.requestStatus,
      updatedAt: saved.updatedAt,
    })
    nextTick(() => { applyingSavedValue = false })
  }
  delete detailCache[saved.id]
  emit('requests-changed')
  savedRevision = revision
  if (automatic) {
    autoSaveState.value = 'saved'
    lastAutoSavedAt.value = businessDateTimeInputValue().slice(11, 16)
  }
  if (editorRevision !== revision) scheduleAutoSave()
  return saved
}

const persistDraft = async (options = {}) => {
  if (activePersistPromise) await activePersistPromise
  const promise = performPersistDraft(options)
  activePersistPromise = promise
  try { return await promise } finally {
    if (activePersistPromise === promise) activePersistPromise = null
  }
}

const scheduleAutoSave = () => {
  clearTimeout(autoSaveTimer)
  if (!editorReady || !dialogVisible.value || submitLocked || editorBusy.value || !canPersistDraft() || editorRevision === savedRevision) return
  autoSaveState.value = 'pending'
  autoSaveTimer = setTimeout(async () => {
    try {
      await persistDraft({ automatic: true })
    } catch (error) {
      autoSaveState.value = 'error'
      console.error('资源需求自动保存失败', error)
    }
  }, 10000)
}

watch(form, () => {
  if (!editorReady || applyingSavedValue) return
  editorRevision += 1
  scheduleAutoSave()
}, { deep: true })

const saveDraftManually = async () => {
  if (submitLocked || editorBusy.value) return
  const creating = !form.id
  submitLocked = true
  clearTimeout(autoSaveTimer)
  saving.value = true
  try {
    const saved = await persistDraft()
    if (!saved) return ElMessage.warning('请先选择来源项目')
    clearDraft()
    dialogVisible.value = false
    ElMessage.success(saved.demandStatus === 'draft' ? '草稿已保存' : '需求内容已保存')
    if (creating) pagination.page = 1
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '保存草稿失败')
  } finally {
    saving.value = false
    submitLocked = false
  }
}

const managementSent = async (saved) => {
  if (saved?.id) { applySavedRequest(saved); emit('requests-changed'); clearDraft(); await fetchData() }
  await sendHistory.refresh()
}

const cancelDemand = async () => {
  if (submitLocked || editorBusy.value) return
  submitLocked = true
  try {
    await ElMessageBox.confirm('取消后将需求状态改为“已取消”，并通知资源开拓需求的原接收人确认收到取消通知。记录将保留，是否继续？', '取消需求', {
      confirmButtonText: '确认取消', cancelButtonText: '返回', type: 'warning',
    })
  } catch { submitLocked = false; return }
  cancelling.value = true
  clearTimeout(autoSaveTimer)
  try {
    await persistDraft()
    const cancelled = await api.cancelResourceRequest(form.id)
    applySavedRequest(cancelled)
    emit('requests-changed')
    clearDraft()
    dialogVisible.value = false
    ElMessage.success('需求已取消')
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '取消需求失败')
  } finally { cancelling.value = false; submitLocked = false; scheduleAutoSave() }
}

const openLifecycleDialog = (resume) => {
  if (!canWrite || submitLocked || editorBusy.value || !form.id) return
  if (resume ? form.demandStatus !== 'paused' : !canPauseDemand(form)) return
  clearTimeout(autoSaveTimer)
  resuming.value = resume
  lifecycleForm.reason = ''
  lifecycleDialog.value = true
  nextTick(() => lifecycleFormRef.value?.clearValidate())
}
const beforeLifecycleClose = done => { if (!lifecycleSaving.value) done() }
const submitLifecycleChange = async () => {
  if (submitLocked || lifecycleSaving.value || !lifecycleDialog.value) return
  submitLocked = true
  lifecycleSaving.value = true
  clearTimeout(autoSaveTimer)
  try {
    await lifecycleFormRef.value?.validate()
    // 保存队列会先等待已发起的自动保存，再保存当前修改；任一步失败都不改变状态。
    const saved = await persistDraft()
    if (!saved) throw new Error('请先选择来源项目')
    const result = resuming.value
      ? await api.resumeResourceRequest(saved.id, saved.updatedAt)
      : await api.pauseResourceRequest(saved.id, lifecycleForm.reason, saved.updatedAt)
    applySavedRequest(result)
    emit('requests-changed')
    delete detailCache[result.id]
    clearDraft()
    lifecycleDialog.value = false
    dialogVisible.value = false
    ElMessage.success(resuming.value ? '需求已恢复' : '需求已暂停')
    await fetchData()
  } catch (error) {
    if (error instanceof Error || error?.detail) ElMessage.error(getLocalizedErrorMessage(error, resuming.value ? '恢复需求失败' : '暂停需求失败'))
  } finally {
    lifecycleSaving.value = false
    submitLocked = false
    scheduleAutoSave()
  }
}

const loadArrangementOptions = async () => {
  if ((!canWrite && !props.arrangementMode) || !hasPermission(['talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate'])) {
    arrangementOptions.can_delegate = false
    return
  }
  Object.assign(arrangementOptions, await developmentApi.options())
}

const openDailyArrangement = async () => {
  if (submitLocked || editorBusy.value || !canArrangeDemand.value) return
  submitLocked = true
  clearTimeout(autoSaveTimer)
  try { await formRef.value.validate() } catch { submitLocked = false; scheduleAutoSave(); return }
  arranging.value = true
  let failure
  try {
    // 重新核对安排权限；保存队列会等待已开始的自动保存，再写入当前内容。
    await loadArrangementOptions()
    if (!arrangementOptions.can_delegate) throw new Error('当前账号没有资源安排权限')
    const saved = await persistDraft()
    if (!saved || saved.demandStatus !== 'confirmed' || saved.requestStatus === 'cancelled') throw new Error('需求已暂停、已取消或尚未发送，请刷新后重试')
    clearDraft()
    const request = await developmentApi.arrangementRequest(saved.id)
    if (request.demand_status !== 'confirmed' || request.request_status === 'cancelled') throw new Error('需求已暂停、已取消或尚未发送，请刷新后重试')
    await arrangementRef.value.open(request, arrangementTomorrow())
  } catch (error) {
    failure = error
    ElMessage.error(getLocalizedErrorMessage(error, '打开每日安排失败，请重试'))
  } finally {
    arranging.value = false
    submitLocked = false
    scheduleAutoSave()
  }
  if (failure) await formRef.value?.applyServerErrors(failure)
}

const openRowArrangement = async (row) => {
  if (arranging.value || row.demandStatus !== 'confirmed' || row.requestStatus === 'cancelled') return
  arranging.value = true
  try {
    await loadArrangementOptions()
    if (!arrangementOptions.can_delegate) throw new Error('当前账号没有资源安排权限')
    const request = await developmentApi.arrangementRequest(row.id)
    await arrangementRef.value.open(request, arrangementTomorrow())
  } catch (error) { ElMessage.error(getLocalizedErrorMessage(error, '打开每日安排失败，请重试')) }
  finally { arranging.value = false }
}
const arrangementSaved = async (day) => {
  for (const key of Object.keys(detailCache)) delete detailCache[key]
  await fetchData()
  emit('arrangement-saved', day)
}
defineExpose({ reload: fetchData })
watch(arrangementVisible, visible => { if (!visible) scheduleAutoSave() })

const flushPendingDraft = async () => {
  clearTimeout(autoSaveTimer)
  if (editorRevision !== savedRevision && canPersistDraft()) {
    try { await persistDraft({ automatic: true }) } catch (error) {
      ElMessage.error(error.detail || '自动保存失败，窗口未关闭')
      return false
    }
  }
  clearDraft()
  return true
}
const requestEditorClose = async () => { if (!submitLocked && !editorBusy.value && await flushPendingDraft()) dialogVisible.value = false }
const beforeEditorClose = async (done) => { if (!submitLocked && !editorBusy.value && await flushPendingDraft()) done() }
const openProgress = (row) => { if (row.demandStatus === 'paused') return ElMessage.warning('请先恢复需求再更新进度'); Object.assign(progressForm, { id: row.id, progressPercent: row.progressPercent, progressNote: '' }); progressDialog.value = true }
const saveProgress = async () => { try { await api.updateResourceProgress(progressForm.id, progressForm); delete detailCache[progressForm.id]; progressDialog.value = false; ElMessage.success('进度已更新'); await fetchData() } catch (error) { ElMessage.error(error.detail || '更新失败') } }

let sourceReady = false, sourceDisposed = false, sourceNavigationSequence = 0
let sourceNavigationQueue = Promise.resolve()
const sourceQueryKey = () => JSON.stringify([route.query.sourceType, route.query.sourceProjectId, route.query.requestCategory])
const handleSourceNavigation = () => {
  if (props.editorOnly) return
  const sequence = ++sourceNavigationSequence
  sourceNavigationQueue = sourceNavigationQueue.then(async () => {
    if (!sourceReady || sourceDisposed || sequence !== sourceNavigationSequence) return
    const sourceType = String(route.query.sourceType || '')
    const sourceProjectId = String(route.query.sourceProjectId || '')
    const requestCategory = String(route.query.requestCategory || '')
    const key = sourceQueryKey()
    if (!sourceProjectId || !Object.hasOwn(sourceLabels, sourceType) || sourceType === 'other') return
    const existing = await api.getResourceRequestBySource(sourceType, sourceProjectId)
    if (sourceDisposed || sequence !== sourceNavigationSequence || key !== sourceQueryKey()) return
    if (existing) await openEditor(existing)
    else await openEditor(null, { sourceType, sourceProjectId, requestCategory })
    if (sourceDisposed || sequence !== sourceNavigationSequence || key !== sourceQueryKey()) return
    const query = { ...route.query }
    delete query.sourceType
    delete query.sourceProjectId
    delete query.requestCategory
    await router.replace({ query, hash: route.hash })
  }).catch(error => { if (!sourceDisposed) ElMessage.error(getLocalizedErrorMessage(error, '打开来源资源需求失败，请重试')) })
  return sourceNavigationQueue
}
watch(sourceQueryKey, handleSourceNavigation)

onMounted(async () => {
  if (props.arrangementMode) loadArrangementOptions().catch(error => ElMessage.error(getLocalizedErrorMessage(error, '加载每日安排权限失败')))
  const listPromise = fetchData()
  const results = await Promise.allSettled([getProjectLanguages(), getUserOptions({ limit: 50 })])
  languages.value = results[0].value || []
  users.value = (results[1].value || []).map((item) => ({ ...item, fullName: item.display_name }))
  Object.assign(form, emptyForm())
  await listPromise
  if (sourceDisposed) return
  if (props.editorOnly) {
    try {
      const source = props.sourceRequest
      if (source?.dispatchBatchId) {
        const request = await api.getResourceDispatchRequest(source.dispatchBatchId)
        if (!sourceDisposed) await openEditor(request)
        return
      }
      if (!source?.sourceProjectId) throw new Error('请选择来源项目')
      const existing = await api.getResourceRequestBySource(source.sourceType, source.sourceProjectId)
      if (sourceDisposed) return
      if (existing) await openEditor(existing)
      else await openEditor(null, source)
    } catch (error) {
      if (!sourceDisposed) {
        ElMessage.error(getLocalizedErrorMessage(error, '打开资源需求失败，请重试'))
        emit('editor-closed')
      }
    }
    return
  }
  sourceReady = true
  await handleSourceNavigation()
})
onBeforeUnmount(() => { sourceDisposed = true; sourceNavigationSequence++; clearTimeout(timer); clearTimeout(autoSaveTimer); clearTimeout(sourceOptionTimer); controller?.abort(); sourceOptionController?.abort() })
</script>

<style scoped>
.resource-request-page { min-height: 0; }
.resource-request-toolbar { margin-bottom: 14px; }
.resource-request-panel .header { justify-content: flex-end; }
.resource-request-panel .header-actions { flex-wrap: wrap; justify-content: flex-end; }
.header, .header-actions, .advanced__header, .section-title, .item-title { display: flex; align-items: center; }
.header, .advanced__header, .section-title, .item-title { justify-content: space-between; }
.header-actions { gap: 8px; }
.header h2 { margin: 0; }
.header p { margin: 4px 0 0; color: var(--el-text-color-secondary); }
.search-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px 10px; margin-bottom: 8px; padding: 8px 10px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-fill-color-extra-light); }
.search-form :deep(.el-form-item) { margin: 0; }
.list-error { margin-bottom: 16px; }
.list-error__content { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.count { margin-left: 5px; padding: 1px 6px; border-radius: 9px; color: #fff; background: var(--el-color-primary); font-size: 11px; }
.advanced { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.advanced__header { position: sticky; top: 0; z-index: 1; margin-bottom: 12px; background: var(--el-bg-color-overlay); }
.pagination { margin-top: 16px; }
.detail { max-height: 560px; overflow-y: auto; }
.associated-project-link { display: inline; height: auto; white-space: normal; text-align: left; line-height: inherit; overflow-wrap: anywhere; }
.request-no-link { display: block; width: 100%; height: auto; min-width: 0; padding: 0; text-align: left; white-space: nowrap; }
.pre { white-space: pre-wrap; word-break: break-word; }
.cell-summary { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-summary { margin-bottom: 16px; }
.lifecycle-bar, .editor-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.lifecycle-bar { margin-bottom: 16px; padding: 10px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-lighter); }
.lifecycle-label { margin-right: 8px; color: var(--el-text-color-secondary); }
.autosave-state { color: var(--el-text-color-secondary); font-size: 12px; }
.autosave-state.is-error { color: var(--el-color-danger); }
.autosave-state.is-saving, .autosave-state.is-pending { color: var(--el-color-primary); }
.editor-footer { width: 100%; flex-wrap: wrap; }
.editor-footer-lifecycle { display: flex; flex-wrap: wrap; gap: 8px; }
.editor-footer-lifecycle .el-button + .el-button { margin-left: 0; }
.lifecycle-hint { margin: 0 0 18px; line-height: 1.7; }
.editor-footer-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.editor-footer-actions .el-button + .el-button { margin-left: 0; }
.items { padding: 14px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; }
.section-hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; font-weight: normal; }
.item-card { margin-top: 12px; padding: 12px; border-radius: 6px; background: var(--el-fill-color-light); }
.item-title { margin-bottom: 10px; font-weight: 600; }
.request-language-row, .request-language-chain, .request-language-node { display: flex; align-items: center; }
.request-language-row { min-width: 0; gap: 12px; }
.request-language-chain { min-width: 0; flex: 1; gap: 8px; overflow-x: auto; padding: 2px 2px 6px; }
.request-language-node { position: relative; min-width: 180px; flex: 0 0 180px; }
.request-language-node .el-select { width: 100%; }
.request-language-node:has(.request-language-remove) :deep(.el-select__wrapper) { padding-right: 34px; }
.request-language-remove { position: absolute; right: 4px; z-index: 1; }
.request-language-arrow { color: var(--el-color-primary); font-size: 20px; font-weight: 700; }
.request-language-count { width: 170px; flex: 0 0 170px; }
.show-detail-row { margin: -4px 0 12px 110px; }
@media (max-width: 767px) { .header { align-items: flex-start; flex-direction: column; gap: 12px; } .header-actions { width: 100%; flex-wrap: wrap; } .search-form :deep(.el-form-item), .search-form :deep(.el-form-item__content), .search-form :deep(.el-input), .search-form :deep(.el-select) { width: 100%; } .show-detail-row { margin-left: 0; } .request-language-row { align-items: stretch; flex-direction: column; } .request-language-count { width: 100%; flex-basis: auto; } }
</style>

<style>
.resource-dialog, .resource-lifecycle-dialog { display: flex; max-height: 90vh; flex-direction: column; overflow: hidden; }
.resource-lifecycle-dialog .el-dialog__header, .resource-lifecycle-dialog .el-dialog__footer { flex-shrink: 0; }
.resource-lifecycle-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.resource-lifecycle-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); }
.resource-dialog .el-dialog__header, .resource-dialog .el-dialog__footer { flex-shrink: 0; }
.resource-dialog .el-dialog__body { flex: 1; min-height: 0; overflow-y: auto; }
.resource-dialog .el-dialog__footer { border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-light); box-shadow: 0 -4px 12px rgb(0 0 0 / 4%); }
.resource-detail-popover, .resource-items-popover { max-width: calc(100vw - 32px) !important; }
@media (max-width: 768px) {
  .resource-detail-popover.el-popper, .resource-items-popover.el-popper {
    position: fixed !important;
    left: 16px !important;
    right: 16px !important;
    width: auto !important;
    max-width: none !important;
    transform: none !important;
  }
}
</style>

<style scoped>
.source-project-reference{display:flex;align-items:center;gap:10px;width:100%;padding:4px 8px;box-sizing:border-box;background:#f1f5f9;border-radius:4px;flex-wrap:wrap}
.source-project-reference>:deep(.el-input){flex:0 0 180px}
.source-project-name{height:auto;white-space:normal;text-align:left;line-height:1.6;max-width:100%;overflow-wrap:anywhere}
.other-request-items{margin-top:12px;border:1px solid #e2e8f0;border-radius:8px;padding:12px}
.other-request-items>summary{cursor:pointer;font-weight:600;color:#475569}
</style>

<style scoped>
.item-card>summary .el-button{float:right;margin-left:12px}
</style>

<style scoped>.request-management-send{border:1px solid #dbe3ef;border-radius:8px;padding:14px;margin:16px 0}.request-management-send>p{font-size:12px;color:#64748b;line-height:1.7}</style>
