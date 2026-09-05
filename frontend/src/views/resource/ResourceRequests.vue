<template>
  <div class="resource-request-page">
    <el-card>
      <template #header>
        <div class="header">
          <div>
            <h2>资源需求管理</h2>
            <p>统一跟踪标注、招聘、口译、笔译及其他资源请求</p>
          </div>
          <div class="header-actions">
            <TableColumnSettings
              v-model="selectedColumnKeys"
              :columns="tableColumns"
              :column-count="2"
              hint="序号和操作列固定显示；客户编号等低频字段默认隐藏，可按需启用。"
              @reset="resetColumns"
            />
            <BatchDeleteToolbar v-if="canWrite" :active="deleteMode" :selected-count="selectedRows.length" :loading="deleting" @enter="enterDeleteMode" @exit="exitDeleteMode" @confirm="confirmBatchDelete" />
            <el-button v-if="canWrite && !deleteMode" type="primary" @click="openEditor()">新增资源需求</el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-input
          v-model="searchForm.keyword"
          clearable
          placeholder="搜索请求编号、项目、客户或需求详情"
          style="width: 330px"
          @input="onKeyword"
          @keyup.enter="search"
        />
        <el-select v-model="filterModel.requestStatus" multiple collapse-tags :max-collapse-tags="1" clearable placeholder="请求状态" style="width: 160px" @change="search">
          <el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" />
        </el-select>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <AdvancedFilterPopover v-model:visible="advancedVisible" :count="advancedCount" popper-class="resource-request-advanced-popover" @clear="clearAdvanced" @reset="reset">
          <CompactFilterGrid :fields="advancedFilterFields" :model="filterModel" @update="updateConfiguredFilter" @text-input="onConfiguredText" @change="search" @enter="search" />
        </AdvancedFilterPopover>
      </div>

      <el-alert v-if="listError" class="list-error" type="error" show-icon :closable="false">
        <template #title>资源需求列表加载失败</template>
        <div class="list-error__content">
          <span>{{ listError }}</span>
          <el-button link type="primary" :loading="loading" @click="fetchData">重新加载</el-button>
        </div>
      </el-alert>

      <el-table ref="tableRef" :data="rows" v-loading="loading" border row-key="id" @selection-change="handleDeleteSelectionChange">
        <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
        <el-table-column type="index" label="序号" width="52" fixed="left" :index="rowIndex" />
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
            <el-popover
              v-if="column.key === 'requestNo'"
              trigger="click"
              placement="left"
              :width="760"
              :fallback-placements="['bottom', 'top', 'right']"
              :popper-options="{ modifiers: [{ name: 'preventOverflow', options: { padding: 16, boundary: 'viewport' } }] }"
              title="资源需求详情"
              popper-class="resource-detail-popover"
              @show="loadDetail(row)"
              @hide="cancelInlineDetailEdit"
            >
              <template #reference>
                <el-button link type="primary" class="business-clickable-cell" :title="`${row.requestNo || '-'}（点击查看详情）`" @click.stop>
                  {{ row.requestNo || '-' }}
                </el-button>
              </template>
              <div class="detail" v-loading="detailLoading === row.id">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="请求编号">{{ detailOf(row).requestNo || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="需求状态">{{ demandStatusLabels[detailOf(row).demandStatus] || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="项目类型">{{ projectTypesText(detailOf(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="项目状态">{{ projectStatusText(detailOf(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="请求状态">{{ statusLabels[detailOf(row).requestStatus] || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="需求项目订单号">{{ detailOf(row).currentOrderNo || detailOf(row).sourceOrderNoSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="需求项目">{{ detailOf(row).currentProjectName || detailOf(row).sourceProjectNameSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="客户编号">{{ detailOf(row).clientCodeSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="客户简称">{{ detailOf(row).clientShortNameSnapshot || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="负责人">{{ ownerName(detailOf(row)) }}</el-descriptions-item>
                  <el-descriptions-item label="优先级">{{ priorityLabels[detailOf(row).priority] || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="发起时间">{{ formatDate(detailOf(row).requestedAt) }}</el-descriptions-item>
                  <el-descriptions-item label="需求详情" :span="2"><InlineTextField :model-value="detailOf(row).requestDetail" :editable="canWrite && !deleteMode" :empty-as-null="false" label="需求详情" multiline :save-field="(value) => saveRequestTextField(row, value)" @conflict="loadDetail(row, true)" /></el-descriptions-item>
                  <el-descriptions-item label="语种、人数及要求" :span="2"><LanguageItemsPopover :items="detailOf(row).items || []" :languages="languages" mode="all" :request-detail="detailOf(row).requestDetail" :always-expanded="true" :editable="canWrite && !deleteMode" :save-item="(item, value) => saveRequestItemTextField(row, item, value)" :on-conflict="() => loadDetail(row, true)" /></el-descriptions-item>
                </el-descriptions>
              </div>
            </el-popover>
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
          </template>
        </el-table-column>
        <el-table-column v-if="canWrite && !deleteMode" label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <PrimaryEditButton @click="openEditor(row)" />
            <el-button link type="primary" @click="openProgress(row)">更新进度</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pagination" v-model:current-page="pagination.page" v-model:page-size="pagination.limit" :total="pagination.total" layout="total, sizes, prev, pager, next" @change="fetchData" />
    </el-card>

    <DraggableFormDialog v-model="dialogVisible" :title="form.id ? '编辑资源需求' : '新增资源需求'" width="min(960px, calc(100vw - 32px))" top="5vh" class="resource-dialog" :before-close="beforeEditorClose" @closed="onEditorClosed">
      <AppForm ref="formRef" :model="form" :rules="formRules" :validate-on-rule-change="false" label-width="110px">
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
          <el-select v-model="form.sourceProjectId" filterable remote :remote-method="searchSourceProjects" style="width: 100%" :loading="sourceOptionsLoading || prefillLoading" @change="sourceProjectChanged">
            <el-option v-for="item in availableProjects" :key="item.id" :label="`${item.orderNo || ''} ${item.projectName || '未命名'}`.trim()" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="其他类型" prop="otherProjectTypes">
          <el-select v-model="form.otherProjectTypes" multiple filterable allow-create default-first-option style="width: 100%" placeholder="输入其他类型后按回车，可添加多个">
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>

        <el-descriptions v-if="sourceInfo.projectName" class="source-summary" title="自动获取的项目信息" :column="2" border size="small">
          <el-descriptions-item label="项目类型">{{ sourceInfo.projectTypes.map(projectTypeLabel).join('、') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">{{ projectStatusLabel(sourceInfo.projectStatus) }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ sourceInfo.orderNo || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目名称">{{ sourceInfo.projectName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户编号">{{ sourceInfo.clientCode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户简称">{{ sourceInfo.clientShortName || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="16">
          <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.priority" style="width: 100%"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item></el-col>
          <el-col :xs="24" :md="12"><el-form-item label="负责人"><el-select v-model="form.ownerId" clearable filterable style="width: 100%"><el-option v-for="user in users" :key="user.id" :label="userName(user)" :value="user.id" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item v-if="form.requestDetail || showRequestDetail" label="需求详情">
          <el-input v-model="form.requestDetail" type="textarea" :rows="4" placeholder="已从来源项目自动获取，可继续补充；无内容时列表自动隐藏" />
        </el-form-item>
        <div v-else class="show-detail-row"><el-button link type="primary" @click="showRequestDetail = true">补充需求详情</el-button></div>

        <section class="items">
          <div class="section-title">
            <div><strong>需求语种、人数及详情</strong><div class="section-hint">已自动获取来源项目内容；方言或未收录语种可直接输入后创建。</div></div>
            <el-button type="primary" plain @click="addItem">添加明细</el-button>
          </div>
          <el-empty v-if="!form.items.length" description="暂无结构化明细" :image-size="64" />
          <div v-for="(item, index) in form.items" :key="item.id || index" class="item-card">
            <div class="item-title"><span>明细 {{ index + 1 }}</span><el-button link type="danger" @click="form.items.splice(index, 1)">删除</el-button></div>
            <div class="request-language-row">
              <div class="request-language-chain">
                <template v-for="(_languageId, languageIndex) in item.languageIds" :key="languageIndex">
                  <span v-if="languageIndex" class="request-language-arrow">↔</span>
                  <div class="request-language-node">
                    <el-select v-model="item.languageIds[languageIndex]" clearable filterable allow-create default-first-option :placeholder="languageIndex ? `语种 ${languageIndex + 1}` : '需求语种/源语种'">
                      <el-option v-for="language in languages" :key="language.id" :label="languageOptionLabel(language)" :value="language.id" />
                    </el-select>
                    <el-button v-if="languageIndex >= 2" class="request-language-remove" link type="danger" :icon="CircleClose" :aria-label="`移除语种 ${languageIndex + 1}`" @click="item.languageIds.splice(languageIndex, 1)" />
                  </div>
                </template>
                <el-button link type="primary" :icon="Plus" :disabled="item.languageIds.length >= 5" @click="item.languageIds.push(null)">{{ item.languageIds.length >= 5 ? '最多 5 个' : '增加语种' }}</el-button>
              </div>
              <el-input-number v-model="item.requiredCount" :min="1" placeholder="需求人数（可空）" class="request-language-count" />
            </div>
            <el-input v-model="item.requirementDetail" type="textarea" :rows="2" placeholder="该语种具体要求；完整需求默认放在第一条明细" style="margin-top: 10px" />
          </div>
        </section>
      </AppForm>
      <template #footer>
        <div class="editor-footer">
          <el-button v-if="form.demandStatus === 'confirmed'" type="danger" plain :loading="cancelling" @click="cancelDemand">取消需求</el-button>
          <span v-else></span>
          <div>
            <el-button :disabled="saving || sending || cancelling" @click="requestEditorClose">关闭</el-button>
            <el-button :loading="saving" :disabled="sending || cancelling" @click="saveDraftManually">保存</el-button>
            <el-button v-if="form.demandStatus !== 'confirmed'" type="primary" :loading="sending" :disabled="saving || cancelling" @click="sendDemand">{{ form.demandStatus === 'cancelled' ? '重新发送' : '发送' }}</el-button>
          </div>
        </div>
      </template>
    </DraggableFormDialog>

    <el-dialog v-model="progressDialog" title="更新资源开拓进度" width="min(520px, calc(100vw - 32px))">
      <AppForm label-width="90px"><el-form-item label="完成比例"><el-slider v-model="progressForm.progressPercent" show-input /></el-form-item><el-form-item label="进度说明"><el-input v-model="progressForm.progressNote" type="textarea" :rows="3" /></el-form-item></AppForm>
      <template #footer><el-button @click="progressDialog = false">取消</el-button><el-button type="primary" @click="saveProgress">保存进度</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElMessage, ElMessageBox, ElPopover, ElTable, ElTableColumn } from 'element-plus'
import { CircleClose, Plus } from '@element-plus/icons-vue'
import * as api from '@/api/resourceRequests'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'
import { getUserOptions } from '@/api/users'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import BatchDeleteToolbar from '@/components/common/BatchDeleteToolbar.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import InlineTextField from '@/components/common/InlineTextField.vue'
import AdvancedFilterPopover from '@/components/common/AdvancedFilterPopover.vue'
import CompactFilterGrid from '@/components/common/CompactFilterGrid.vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import { useTableColumns } from '@/composables/useTableColumns'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { useFormDraft } from '@/composables/useFormDraft'
import { hasPermission } from '@/utils/permission'
import { formatDateTimeMinute as formatDate, formatTimeMinute } from '@/utils/dateTime'
import { countActiveFilters, createFilterModel, resetFilterModel, serializeFieldFilters } from '@/utils/listFieldFilters'
import { getCachedOptions } from '@/utils/optionCache'

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
const saving = ref(false)
const sending = ref(false)
const cancelling = ref(false)
const autoSaveState = ref('idle')
const lastAutoSavedAt = ref('')
let submitLocked = false
const detailLoading = ref('')
const detailCache = reactive({})
const showRequestDetail = ref(false)
const formRef = ref(null)
const pagination = reactive({ page: 1, limit: 10, total: 0 })
const tableRef = ref(null)
const canWrite = hasPermission('projects:write')
const searchForm = reactive({ keyword: '' })
const form = reactive({})
const sourceInfo = reactive({ projectTypes: [], orderNo: '', projectName: '', projectStatus: '', clientCode: '', clientShortName: '' })
const progressForm = reactive({ id: '', progressPercent: 0, progressNote: '' })

const sourceLabels = { annotation: '标注', recruitment: '招聘', interpretation: '口译', translation: '笔译', other: '其他' }
const categoryLabels = { annotation_trial: '标注试标', annotation_formal: '标注正式', recruitment: '招聘', interpretation: '口译', translation: '笔译', other: '其他' }
const statusLabels = { draft: '草稿', submitted: '已提交', in_progress: '进行中', fulfilled: '已完成', cancelled: '已取消' }
const demandStatusLabels = { draft: '草稿准备中', confirmed: '需求确认', cancelled: '需求取消' }
const priorityLabels = { high: '高', medium: '中', low: '低' }
const projectTypeLabels = {
  audio_collection: '音频采集', audio_annotation: '音频标注', audio_evaluation: '音频评测', text_evaluation: '文本评测', text_annotation: '文本标注', quality_inspection: '质检', listening_test: '测听', slot_deduction: '扣槽', generalization: '泛化', translation: '翻译', ai_evaluation: 'ai评测',
  onsite: '现场口译', booth: '展会摊位口译', exhibition_escort: '展会陪同口译', escort: '陪同口译', small_business_meeting: '小型商务会议口译', small_non_business_meeting: '小型（非商务）会议口译', consecutive: '会议交传口译', simultaneous: '会议同传口译', online_meeting: '线上会议口译', online_simultaneous: '线上同传口译',
}
const projectStatusLabels = {
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果', resource_sourcing: '资源开拓', resource_sourcing_cancelled: '取消资源开拓', trial_preparation: '试标准备', trial_in_progress: '试标中', trial_passed: '试标通过', trial_failed: '试标未通过', trial_partially_passed: '部分试标通过', project_in_progress: '项目进行中', sent_to_client: '已发客户', client_feedback: '客户反馈', partially_cancelled: '已部分取消',
  pending_setup: '待启动', sourcing: '寻访中', recommending: '推荐中', interviewing: '面试中', offer_negotiation: 'Offer协商中', pending_onboard: '待入职', probation: '试用期', full_time_dispatch: '全职外派', cancelled: '项目取消', closed: '已关闭',
  initial_follow_up: '初步跟进中', in_progress: '进行中', ended: '已结束', settled: '已结款', active: '进行中', completed: '已完成', cancelled: '已取消',
  pending_confirmation: '待确认', confirmed: '已确认', organized: '已整理', translator_assigned: '已排译员', sent_to_translator: '已发译员', translator_returned: '译员发回', special_checked: '已专检', typeset: '已排版', special_checked_typeset: '已专检排版', reviewed: '已审核', feedback_sent_to_client: '反馈后发客户', paused: '已暂停',
}

const optionsOf = (map) => Object.entries(map).map(([value, label]) => ({ value, label }))
const filterFields = [
  { key: 'requestNo', label: '请求编号', type: 'text' },
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
  { key: 'requestNo', label: '请求编号', width: 130 },
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
const legacyDefaultColumnKeys = ['projectType', 'projectStatus', 'projectName', 'clientShortName', 'languages', 'requiredCount', 'requestDetail']
const defaultColumnKeys = ['requestNo', 'demandStatus', ...legacyDefaultColumnKeys]
const { selectedKeys: selectedColumnKeys, reset: resetColumns } = useTableColumns(
  'resource-requests',
  tableColumns,
  defaultColumnKeys,
  { legacyDefaultKeys: [legacyDefaultColumnKeys, ['requestNo', ...legacyDefaultColumnKeys]] }
)
const {deleteMode,deleting,selectedRows,enterDeleteMode,exitDeleteMode,handleDeleteSelectionChange,confirmBatchDelete}=useBatchDelete({rows,tableRef,pagination,deleteRow:(row)=>api.deleteResourceRequest(row.id),getLabel:(row)=>row.requestNo||row.currentProjectName||row.id,reload:()=>fetchData(),onDeleted:(row)=>{delete detailCache[row.id]},entityName:'资源需求'})
const visibleColumns = computed(() => tableColumns.filter((column) => selectedColumnKeys.value.includes(column.key)))
const advancedCount = computed(() => countActiveFilters(filterModel, advancedFilterFields))
const headerFilterKeys = new Set(defaultColumnKeys)
const headerFilterDefinition = (key) => headerFilterKeys.has(key) ? filterFields.find((item) => item.key === key) : null
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
const emptyForm = () => ({ id: '', sourceType: 'annotation', requestCategory: 'annotation_trial', sourceProjectId: '', otherProjectTypes: [], requestDetail: '', priority: 'medium', requestStatus: 'draft', demandStatus: 'draft', ownerId: '', items: [] })
const { beginDraft, pauseDraft, clearDraft } = useFormDraft({ namespace: 'resource-request', form, createDefault: emptyForm, formRef })
const resetSourceInfo = () => Object.assign(sourceInfo, { projectTypes: [], orderNo: '', projectName: '', projectStatus: '', clientCode: '', clientShortName: '' })
const params = () => ({ keyword: searchForm.keyword.trim() || undefined, field_filters: serializeFieldFilters(filterModel, filterFields) })
const fetchData = async () => {
  controller?.abort()
  controller = new AbortController()
  const current = ++requestId
  loading.value = true
  listError.value = ''
  try {
    const filters = params()
    const page = await api.getResourceRequestPage(
      { skip: (pagination.page - 1) * pagination.limit, limit: pagination.limit, ...filters },
      { signal: controller.signal },
    )
    if (current !== requestId) return
    rows.value = page?.items || []
    pagination.total = page?.total || 0
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
const onKeyword = (value) => { clearTimeout(timer); if (!value) return search(); timer = setTimeout(search, 400) }
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
const demandStatusType = (value) => ({ draft: 'info', confirmed: 'success', cancelled: 'danger' }[value] || 'info')
const editorDemandStatusText = computed(() => form.demandStatus === 'confirmed' ? '需求已发送' : form.demandStatus === 'cancelled' ? '需求已取消' : '草稿准备中')
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
const sourceProjectChanged = async (projectId) => {
  if (!projectId) return resetSourceInfo()
  prefillLoading.value = true
  try {
    const value = await api.getResourceRequestSourcePrefill(form.sourceType, projectId)
    form.requestCategory = value.requestCategory || form.requestCategory
    Object.assign(sourceInfo, { projectTypes: value.sourceProjectTypes || [], orderNo: value.orderNo || '', projectName: value.projectName || '', projectStatus: value.projectStatus || '', clientCode: value.clientCode || '', clientShortName: value.clientShortName || '' })
    form.requestDetail = value.requestDetail || ''
    form.items = (value.items || []).map((item) => ({ id: null, languageIds: item.languageIds?.length ? [...item.languageIds] : [item.sourceLanguageId, item.targetLanguageId].filter(Boolean), requiredCount: item.requiredCount || null, requirementDetail: item.requirementDetail || '' }))
    showRequestDetail.value = Boolean(form.requestDetail)
  } catch (error) { ElMessage.error(error.detail || '自动获取项目需求信息失败') } finally { prefillLoading.value = false }
}
const openEditor = async (row = null, source = null) => {
  if (!row?.id) api.resetResourceRequestIdempotency()
  let value = row
  if (row?.id) value = await api.getResourceRequest(row.id)
  editorReady = false
  Object.assign(form, emptyForm(), value || {})
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
  await loadSourceOptions()
  if (form.sourceProjectId && !availableProjects.value.some((item) => item.id === form.sourceProjectId)) {
    projects[form.sourceType].unshift({ id: form.sourceProjectId, orderNo: sourceInfo.orderNo, projectName: sourceInfo.projectName, projectStatus: sourceInfo.projectStatus, clientShortName: sourceInfo.clientShortName })
  }
  showRequestDetail.value = Boolean(form.requestDetail)
  dialogVisible.value = true
  if (source?.sourceProjectId) await sourceProjectChanged(source.sourceProjectId)
  await nextTick()
  const draftKey = value?.id
    ? `edit:${value.id}`
    : source?.sourceProjectId
      ? `create:${source.sourceType}:${source.sourceProjectId}`
      : 'create'
  await beginDraft(draftKey)
  editorRevision = 0
  savedRevision = 0
  autoSaveState.value = 'idle'
  lastAutoSavedAt.value = ''
  editorReady = true
}
const resetEditor = () => { formRef.value?.clearValidate(); Object.assign(form, emptyForm()); resetSourceInfo(); showRequestDetail.value = false }
const onEditorClosed = () => { editorReady = false; clearTimeout(autoSaveTimer); pauseDraft(); resetEditor() }
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
  const data = { sourceType: form.sourceType, requestCategory: form.requestCategory, annotationProjectId: null, recruitmentProjectId: null, interpretationProjectId: null, translationProjectId: null, otherSourceName: form.sourceType === 'other' ? form.otherProjectTypes.map((item) => item.trim()).filter(Boolean).join(',') : null, requestDetail: form.requestDetail.trim(), priority: form.priority, requestStatus: form.requestStatus, ownerId: form.ownerId || null, items: await normalizeItems() }
  if (form.sourceType !== 'other') data[`${form.sourceType}ProjectId`] = form.sourceProjectId
  return data
}
const scrollToFirstError = () => requestAnimationFrame(() => document.querySelector('.resource-dialog .el-form-item.is-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
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
  if (!form.id) data.requestStatus = 'draft'
  const saved = form.id ? await api.updateResourceRequest(form.id, data) : await api.createResourceRequest(data)
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
  savedRevision = revision
  if (automatic) {
    autoSaveState.value = 'saved'
    lastAutoSavedAt.value = formatTimeMinute(new Date())
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
  if (!editorReady || !dialogVisible.value || !canPersistDraft() || editorRevision === savedRevision) return
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
  if (submitLocked) return
  submitLocked = true
  clearTimeout(autoSaveTimer)
  saving.value = true
  try {
    const saved = await persistDraft()
    if (!saved) return ElMessage.warning('请先选择来源项目')
    clearDraft()
    dialogVisible.value = false
    ElMessage.success(saved.demandStatus === 'draft' ? '草稿已保存' : '需求内容已保存')
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '保存草稿失败')
  } finally {
    saving.value = false
    submitLocked = false
  }
}

const sendDemand = async () => {
  if (submitLocked) return
  submitLocked = true
  clearTimeout(autoSaveTimer)
  try { await formRef.value?.validate() } catch { submitLocked = false; scrollToFirstError(); return }
  sending.value = true
  try {
    const saved = await persistDraft()
    if (!saved) throw new Error('请先选择来源项目')
    const sent = await api.sendResourceRequest(saved.id)
    applySavedRequest(sent)
    clearDraft()
    dialogVisible.value = false
    ElMessage.success('需求已发送')
    await fetchData()
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '发送需求失败'))
  } finally {
    sending.value = false
    submitLocked = false
  }
}

const cancelDemand = async () => {
  try {
    await ElMessageBox.confirm('取消后资源需求记录将保留，并标记为“需求取消”。是否继续？', '取消需求', {
      confirmButtonText: '确认取消', cancelButtonText: '返回', type: 'warning',
    })
  } catch { return }
  cancelling.value = true
  try {
    const cancelled = await api.cancelResourceRequest(form.id)
    applySavedRequest(cancelled)
    clearDraft()
    dialogVisible.value = false
    ElMessage.success('需求已取消')
    await fetchData()
  } catch (error) {
    ElMessage.error(error.detail || '取消需求失败')
  } finally { cancelling.value = false }
}

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
const requestEditorClose = async () => { if (await flushPendingDraft()) dialogVisible.value = false }
const beforeEditorClose = async (done) => { if (await flushPendingDraft()) done() }
const openProgress = (row) => { Object.assign(progressForm, { id: row.id, progressPercent: row.progressPercent, progressNote: '' }); progressDialog.value = true }
const saveProgress = async () => { try { await api.updateResourceProgress(progressForm.id, progressForm); delete detailCache[progressForm.id]; progressDialog.value = false; ElMessage.success('进度已更新'); await fetchData() } catch (error) { ElMessage.error(error.detail || '更新失败') } }

onMounted(async () => {
  const listPromise = fetchData()
  const results = await Promise.allSettled([getProjectLanguages(), getUserOptions({ limit: 50 })])
  languages.value = results[0].value || []
  users.value = (results[1].value || []).map((item) => ({ ...item, fullName: item.display_name }))
  Object.assign(form, emptyForm())
  await listPromise
  const sourceType = String(route.query.sourceType || '')
  const sourceProjectId = String(route.query.sourceProjectId || '')
  if (sourceProjectId && Object.hasOwn(sourceLabels, sourceType) && sourceType !== 'other') {
    const existing = await api.getResourceRequestBySource(sourceType, sourceProjectId)
    if (existing) await openEditor(existing)
    else await openEditor(null, { sourceType, sourceProjectId, requestCategory: String(route.query.requestCategory || '') })
    const query = { ...route.query }
    delete query.sourceType
    delete query.sourceProjectId
    delete query.requestCategory
    await router.replace({ query })
  }
})
onBeforeUnmount(() => { clearTimeout(timer); clearTimeout(autoSaveTimer); clearTimeout(sourceOptionTimer); controller?.abort(); sourceOptionController?.abort() })
</script>

<style scoped>
.resource-request-page { min-height: 0; }
.header, .header-actions, .filters, .advanced__header, .section-title, .item-title { display: flex; align-items: center; }
.header, .advanced__header, .section-title, .item-title { justify-content: space-between; }
.header-actions, .filters { gap: 8px; }
.header h2 { margin: 0; }
.header p { margin: 4px 0 0; color: var(--el-text-color-secondary); }
.filters { margin-bottom: 16px; flex-wrap: wrap; }
.list-error { margin-bottom: 16px; }
.list-error__content { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.count { margin-left: 5px; padding: 1px 6px; border-radius: 9px; color: #fff; background: var(--el-color-primary); font-size: 11px; }
.advanced { max-height: min(560px, calc(100vh - 120px)); overflow-y: auto; }
.advanced__header { position: sticky; top: 0; z-index: 1; margin-bottom: 12px; background: var(--el-bg-color-overlay); }
.pagination { margin-top: 16px; }
.detail { max-height: 560px; overflow-y: auto; }
.pre { white-space: pre-wrap; word-break: break-word; }
.cell-summary { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-summary { margin-bottom: 16px; }
.lifecycle-bar, .editor-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.lifecycle-bar { margin-bottom: 16px; padding: 10px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; background: var(--el-fill-color-lighter); }
.lifecycle-label { margin-right: 8px; color: var(--el-text-color-secondary); }
.autosave-state { color: var(--el-text-color-secondary); font-size: 12px; }
.autosave-state.is-error { color: var(--el-color-danger); }
.autosave-state.is-saving, .autosave-state.is-pending { color: var(--el-color-primary); }
.editor-footer { width: 100%; }
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
@media (max-width: 767px) { .header { align-items: flex-start; flex-direction: column; gap: 12px; } .header-actions { width: 100%; flex-wrap: wrap; } .show-detail-row { margin-left: 0; } .request-language-row { align-items: stretch; flex-direction: column; } .request-language-count { width: 100%; flex-basis: auto; } }
</style>

<style>
.resource-dialog { display: flex; max-height: 90vh; flex-direction: column; overflow: hidden; }
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
