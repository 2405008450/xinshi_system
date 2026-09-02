<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>译员资源库</span>
        <div class="header-actions">
          <TableColumnSettings
            v-model="visibleColumnKeys"
            :columns="translatorTableColumns"
            :column-count="2"
            @reset="resetColumns"
          />
          <el-button @click="demoImportVisible = true">导入排期Demo</el-button>
          <el-button type="primary" @click="handleAdd">新增译员</el-button>
        </div>
      </div>
    </template>

    <div class="search-area">
      <AppForm :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="姓名">
          <el-input
            v-model="searchForm.translator_name"
            placeholder="请输入译员姓名"
            clearable
            style="width: 200px"
            @input="handleTextFilterInput"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="全部状态"
            clearable
            style="width: 140px"
            @change="handleSelectionFilterChange"
          >
            <el-option label="活跃" value="active" />
            <el-option label="备用" value="standby" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-popover
            v-model:visible="advancedFilterVisible"
            trigger="click"
            placement="bottom-end"
            :width="760"
            popper-class="translator-advanced-filter-popper"
          >
            <template #reference>
              <el-button>
                高级筛选
                <el-badge
                  v-if="advancedFilterCount"
                  :value="advancedFilterCount"
                  class="advanced-filter-badge"
                />
              </el-button>
            </template>
            <div class="advanced-filter-panel">
              <div class="advanced-filter-title">高级筛选</div>
              <AppForm :model="advancedFilters" label-width="104px" class="advanced-filter-form">
                <el-row :gutter="16">
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="译员编号">
                      <el-input v-model="advancedFilters.translator_code" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="语种">
                      <el-input v-model="advancedFilters.languages" placeholder="如：中英、中日" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="可接稿时段">
                      <el-input v-model="advancedFilters.available_time_slot" placeholder="如：上午、全天" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="领域">
                      <el-input v-model="advancedFilters.domain_keyword" placeholder="如：法律、银行" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="方向">
                      <el-select v-model="advancedFilters.direction" placeholder="全部方向" clearable style="width: 100%" @change="handleSelectionFilterChange">
                        <el-option label="中译外" value="中译外" />
                        <el-option label="外译中" value="外译中" />
                        <el-option label="双向" value="双向" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="合作形式">
                      <el-select v-model="advancedFilters.cooperation_type" placeholder="全部形式" clearable style="width: 100%" @change="handleSelectionFilterChange">
                        <el-option label="全职" value="全职" />
                        <el-option label="兼职" value="兼职" />
                        <el-option label="自由职业" value="自由职业" />
                        <el-option label="外包" value="外包" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="翻译类型">
                      <el-select v-model="advancedFilters.translation_type" placeholder="全部类型" clearable style="width: 100%" @change="handleSelectionFilterChange">
                        <el-option label="口译" value="口译" />
                        <el-option label="笔译" value="笔译" />
                        <el-option label="同传" value="同传" />
                        <el-option label="交传" value="交传" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="质量评分">
                      <el-input v-model="advancedFilters.quality_score" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="联系方式">
                      <el-input v-model="advancedFilters.contact_keyword" placeholder="电话、邮箱或其他联系方式" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="性别">
                      <el-input v-model="advancedFilters.gender" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="国籍">
                      <el-input v-model="advancedFilters.nationality" clearable @input="handleTextFilterInput" @keyup.enter="handleSearch" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="支持云编辑">
                      <el-select v-model="advancedFilters.can_cloud_edit" placeholder="不限" clearable style="width: 100%" @change="handleSelectionFilterChange">
                        <el-option label="是" :value="true" />
                        <el-option label="否" :value="false" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="支持审校">
                      <el-select v-model="advancedFilters.can_revision" placeholder="不限" clearable style="width: 100%" @change="handleSelectionFilterChange">
                        <el-option label="是" :value="true" />
                        <el-option label="否" :value="false" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="优先级范围">
                      <div class="number-range-filter">
                        <el-input-number v-model="advancedFilters.default_priority_min" :min="0" placeholder="最低" controls-position="right" @change="handleSelectionFilterChange" />
                        <span>至</span>
                        <el-input-number v-model="advancedFilters.default_priority_max" :min="0" placeholder="最高" controls-position="right" @change="handleSelectionFilterChange" />
                      </div>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="日产能范围">
                      <div class="number-range-filter">
                        <el-input-number v-model="advancedFilters.daily_word_capacity_min" :min="0" placeholder="最低" controls-position="right" @change="handleSelectionFilterChange" />
                        <span>至</span>
                        <el-input-number v-model="advancedFilters.daily_word_capacity_max" :min="0" placeholder="最高" controls-position="right" @change="handleSelectionFilterChange" />
                      </div>
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="排期待更新">
                      <div class="stale-filter-row">
                        <el-checkbox v-model="advancedFilters.stale_only" @change="handleSelectionFilterChange">仅看待更新</el-checkbox>
                        <el-input-number
                          v-model="advancedFilters.stale_days"
                          :min="1"
                          :max="30"
                          :disabled="!advancedFilters.stale_only"
                          controls-position="right"
                          @change="handleStaleDaysChange"
                        />
                        <span class="stale-days-unit">天</span>
                      </div>
                    </el-form-item>
                  </el-col>
                </el-row>
              </AppForm>
              <div class="advanced-filter-actions">
                <el-button link type="primary" @click="clearAdvancedFilters">清空高级条件</el-button>
                <el-button @click="advancedFilterVisible = false">关闭</el-button>
              </div>
            </div>
          </el-popover>
        </el-form-item>
      </AppForm>
    </div>

    <!-- 主表格 -->
    <el-table
      :data="tableData"
      v-loading="loading"
      border
      :default-sort="{ prop: 'availability_updated_at', order: 'descending' }"
      @sort-change="handleSortChange"
    >
      <el-table-column
        v-for="column in visibleBusinessColumns"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        :min-width="column.minWidth"
        :sortable="column.sortable"
        :show-overflow-tooltip="column.showOverflowTooltip"
      >
        <template #default="{ row }">
          <el-tag v-if="column.type === 'status'" :type="statusTagType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
          <template v-else-if="column.type === 'domain' && row.domain_skills && row.domain_skills.length">
            <el-tag
              v-for="(skill, idx) in row.domain_skills"
              :key="idx"
              :type="domainTagType(skill.level)"
              size="small"
              class="domain-tag"
            >
              {{ skill.domain }}:{{ skill.level }}
            </el-tag>
          </template>
          <span v-else-if="column.type === 'domain'" class="text-muted">-</span>
          <span v-else-if="column.type === 'boolean'">{{ formatBooleanValue(row[column.key]) }}</span>
          <span v-else-if="column.type === 'datetime'">{{ formatDetailDatetime(row[column.key]) }}</span>
          <span v-else>{{ displayValue(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" width="100" fixed="right">
        <template #default="{ row }">
          <DetailPopover :row="row" title="译员详情" :items="detailItems" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="88" fixed="right" align="center">
        <template #default="{ row }">
          <TableActionButton action="edit" @click="handleEdit(row)" />
          <TableActionButton action="delete" @click="handleDelete(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.limit"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="fetchData"
      style="margin-top: 20px"
    />

    <!-- ========== 编辑弹窗 ========== -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      class="translator-dialog"
      width="min(960px, calc(100vw - 32px))"
      top="5vh"
      @close="resetForm"
    >
      <AppForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="110px"
      >
        <div class="form-section-title">基础信息</div>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="姓名" prop="translator_name">
              <el-input v-model="form.translator_name" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="译员编号" prop="translator_code">
              <el-input v-model="form.translator_code" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="活跃" value="active" />
                <el-option label="备用" value="standby" />
                <el-option label="停用" value="inactive" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="口译水平" prop="interpretation_level">
              <el-select v-model="form.interpretation_level" placeholder="请选择" clearable style="width: 100%">
                <el-option label="初级" value="初级" />
                <el-option label="中级" value="中级" />
                <el-option label="高级" value="高级" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="合作形式" prop="cooperation_type">
              <el-select v-model="form.cooperation_type" placeholder="请选择" style="width: 100%">
                <el-option label="全职" value="全职" />
                <el-option label="兼职" value="兼职" />
                <el-option label="自由职业" value="自由职业" />
                <el-option label="外包" value="外包" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="语种" prop="languages">
              <el-input v-model="form.languages" placeholder="如：中英、中日" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="翻译类型" prop="translation_type">
              <el-select v-model="form.translation_type" placeholder="请选择" style="width: 100%">
                <el-option label="口译" value="口译" />
                <el-option label="笔译" value="笔译" />
                <el-option label="同传" value="同传" />
                <el-option label="交传" value="交传" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="质量评分" prop="quality_score">
              <el-input v-model="form.quality_score" placeholder="如 73 / 80 / A" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="默认优先级" prop="default_priority">
              <el-input-number v-model="form.default_priority" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="联系信息" prop="contact_info">
              <el-input v-model="form.contact_info" placeholder="常用联系方式备注" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="方向" prop="direction">
              <el-select v-model="form.direction" placeholder="请选择" style="width: 100%">
                <el-option label="中译外" value="中译外" />
                <el-option label="外译中" value="外译中" />
                <el-option label="双向" value="双向" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="form.remarks" type="textarea" :rows="2" />
        </el-form-item>
        <div class="form-section-title">领域能力</div>
        <div class="domain-skills-editor">
          <el-table :data="form.domain_skills" border size="small" style="margin-bottom: 10px">
            <el-table-column label="领域" min-width="160">
              <template #default="{ row }">
                <el-input v-model="row.domain" placeholder="如：法律、银行、医学" />
              </template>
            </el-table-column>
            <el-table-column label="能力等级" min-width="180">
              <template #default="{ row }">
                <el-input v-model="row.level" placeholder="如：擅长、需审改、一般" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="removeDomainSkill($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" link @click="addDomainSkill">+ 新增领域</el-button>
        </div>
        <div class="form-section-title">补充信息</div>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="联系电话1" prop="phone">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="联系电话2" prop="phone2">
              <el-input v-model="form.phone2" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="其他联系方式" prop="other_contact">
              <el-input v-model="form.other_contact" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="邮箱1" prop="email1">
              <el-input v-model="form.email1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="邮箱2" prop="email2">
              <el-input v-model="form.email2" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="初次沟通时间" prop="first_contact_date">
              <el-date-picker
                v-model="form.first_contact_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择日期"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="性别" prop="gender">
              <el-input v-model="form.gender" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="国籍" prop="nationality">
              <el-input v-model="form.nationality" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="民族" prop="ethnicity">
              <el-input v-model="form.ethnicity" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="身高" prop="height">
              <el-input v-model="form.height" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="形象" prop="appearance">
              <el-input v-model="form.appearance" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="简历路径" prop="resume_path">
              <el-input v-model="form.resume_path" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="总评" prop="overall_rating">
          <el-input v-model="form.overall_rating" type="textarea" :rows="2" />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="demoImportVisible" title="导入排期 Demo" width="860px" @closed="resetDemoImportState">
      <div class="demo-import-panel">
        <p class="demo-import-tip">
          现按这版完整导出结构固定识别 `G/H/I/J/K/L/M/N/O/P`。其中 `I=1` 表示进入按日判断，实际是否可接稿仍以 `K-O` 的 `0/1` 为准；`I=2` 表示未来一个排期周期都不可接稿。`K` 与 `H` 为同一天，`L/M/N/O` 依次表示 `n+1/n+2/n+3/n+4` 天，且 `0=不能接稿`、`1=能接稿`；`J` 作为时段原值保留，`P` 作为备注原值保留。
        </p>
        <input
          ref="demoImportInput"
          type="file"
          accept=".xlsx"
          @change="handleDemoFileChange"
        />
        <div class="demo-import-actions">
          <span class="demo-file-name">{{ demoImportFileName || '未选择文件' }}</span>
          <el-checkbox v-model="demoImportOverwrite">覆盖同日期已有排期</el-checkbox>
        </div>
        <div class="demo-import-toolbar">
          <el-button :loading="demoPreviewLoading" @click="previewDemoImport">生成预览</el-button>
          <span v-if="demoImportPreview" class="demo-preview-summary">
            预览 {{ demoImportPreview.preview_count || 0 }} 条，匹配 {{ demoImportPreview.matched_translators || 0 }} 位译员
          </span>
        </div>
        <el-table
          v-if="demoImportPreview?.preview_items?.length"
          :data="demoImportPreview.preview_items"
          border
          size="small"
          max-height="320"
        >
          <el-table-column prop="translator_name" label="译员" min-width="120" />
          <el-table-column prop="fill_date" label="填报日期" width="110" />
          <el-table-column prop="schedule_date" label="日期" width="110" />
          <el-table-column prop="acceptance_status" label="接稿状态" width="120" />
          <el-table-column prop="available_time_slot" label="导入结果" min-width="150" />
          <el-table-column prop="time_slot" label="时段" min-width="140" show-overflow-tooltip />
          <el-table-column label="动作" width="90">
            <template #default="{ row }">
              <el-tag :type="row.action === 'update' ? 'warning' : 'success'" size="small">
                {{ row.action === 'update' ? '覆盖' : '新增' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="existing_available_time_slot" label="原排期" min-width="120" />
          <el-table-column prop="note" label="备注" min-width="140" show-overflow-tooltip />
        </el-table>
        <el-alert
          v-if="demoImportResult"
          type="success"
          :closable="false"
          show-icon
          style="margin-top: 16px"
        >
          <template #title>
            已处理 {{ demoImportResult.imported_rows || 0 }} 行，匹配 {{ demoImportResult.matched_translators || 0 }} 位译员，
            新增 {{ demoImportResult.created_records || 0 }} 条，更新 {{ demoImportResult.updated_records || 0 }} 条。
          </template>
          <div v-if="demoImportResult.unmatched_names?.length" class="demo-unmatched">
            未匹配姓名：{{ demoImportResult.unmatched_names.join('，') }}
          </div>
        </el-alert>
        <el-alert
          v-else-if="demoImportPreview?.unmatched_names?.length"
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            预览阶段发现未匹配姓名：{{ demoImportPreview.unmatched_names.join('，') }}
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="closeDemoImportDialog">取消</el-button>
        <el-button type="primary" :loading="demoImportLoading" :disabled="!demoImportPreview?.preview_items?.length" @click="submitDemoImport">确认导入</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElButton, ElDescriptions, ElDescriptionsItem, ElMessage, ElMessageBox, ElPopover, ElTag } from 'element-plus'
import * as translatorApi from '@/api/translators'
import * as scheduleApi from '@/api/schedule'
import { formatDateTimeMinute as formatDetailDatetime } from '@/utils/dateTime'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumns } from '@/composables/useTableColumns'

const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增译员')
const formRef = ref(null)

const tableData = ref([])
const pagination = reactive({ page: 1, limit: 20, total: 0 })

const translatorTableColumns = [
  { key: 'default_priority', label: '优先级', width: 80, sortable: true },
  { key: 'status', label: '状态', width: 80, type: 'status' },
  { key: 'translator_code', label: '译员编号', width: 140, showOverflowTooltip: true },
  { key: 'translator_name', label: '姓名', width: 100 },
  { key: 'cooperation_type', label: '合作形式', width: 100 },
  { key: 'translation_type', label: '翻译类型', width: 100 },
  { key: 'interpretation_level', label: '口译水平', width: 100 },
  { key: 'quality_score', label: '质量评分', width: 90 },
  { key: 'languages', label: '语种', width: 100, showOverflowTooltip: true },
  { key: 'direction', label: '方向', width: 90 },
  { key: 'domain_skills', label: '领域能力', minWidth: 180, type: 'domain' },
  { key: 'available_time_slot', label: '可接稿时段', width: 130, showOverflowTooltip: true },
  { key: 'daily_accept_count', label: '日接单数', width: 100 },
  { key: 'hourly_speed', label: '每小时时速', width: 110 },
  { key: 'daily_word_capacity', label: '每日字数产能', width: 120 },
  { key: 'can_cloud_edit', label: '支持云编辑', width: 100, type: 'boolean' },
  { key: 'can_revision', label: '支持审校', width: 100, type: 'boolean' },
  { key: 'overdue_count', label: '逾期次数', width: 90 },
  { key: 'contact_info', label: '联系信息', width: 160, showOverflowTooltip: true },
  { key: 'phone', label: '联系电话1', width: 130, showOverflowTooltip: true },
  { key: 'phone2', label: '联系电话2', width: 130, showOverflowTooltip: true },
  { key: 'email1', label: '邮箱1', width: 180, showOverflowTooltip: true },
  { key: 'email2', label: '邮箱2', width: 180, showOverflowTooltip: true },
  { key: 'other_contact', label: '其他联系方式', width: 160, showOverflowTooltip: true },
  { key: 'gender', label: '性别', width: 80 },
  { key: 'nationality', label: '国籍', width: 100 },
  { key: 'ethnicity', label: '民族', width: 100 },
  { key: 'height', label: '身高', width: 90 },
  { key: 'appearance', label: '形象', width: 140, showOverflowTooltip: true },
  { key: 'resume_path', label: '简历路径', width: 220, showOverflowTooltip: true },
  { key: 'first_contact_date', label: '初次沟通时间', width: 170, type: 'datetime' },
  { key: 'availability_updated_at', label: '排期更新时间', width: 170, type: 'datetime' },
  { key: 'schedule_remarks', label: '排期备注', width: 200, showOverflowTooltip: true },
  { key: 'overall_rating', label: '总评', width: 220, showOverflowTooltip: true },
  { key: 'remarks', label: '备注', width: 220, showOverflowTooltip: true }
]
const defaultTranslatorColumnKeys = [
  'default_priority',
  'status',
  'translator_name',
  'translation_type',
  'interpretation_level',
  'quality_score',
  'languages',
  'direction',
  'domain_skills',
  'remarks'
]
const {
  selectedKeys: visibleColumnKeys,
  isVisible: isColumnVisible,
  reset: resetColumns
} = useTableColumns('resource-translators', translatorTableColumns, defaultTranslatorColumnKeys)
const visibleBusinessColumns = computed(() => translatorTableColumns.filter((column) => isColumnVisible(column.key)))

const defaultSearchForm = {
  translator_name: '',
  status: ''
}

const createDefaultAdvancedFilters = () => ({
  translator_code: '',
  cooperation_type: '',
  languages: '',
  available_time_slot: '',
  domain_keyword: '',
  translation_type: '',
  direction: '',
  quality_score: '',
  contact_keyword: '',
  gender: '',
  nationality: '',
  can_cloud_edit: null,
  can_revision: null,
  default_priority_min: null,
  default_priority_max: null,
  daily_word_capacity_min: null,
  daily_word_capacity_max: null,
  stale_only: false,
  stale_days: 4
})

const searchForm = reactive({ ...defaultSearchForm })
const advancedFilters = reactive(createDefaultAdvancedFilters())
const advancedFilterVisible = ref(false)
const advancedFilterCount = computed(() => {
  const countedKeys = [
    'translator_code',
    'cooperation_type',
    'languages',
    'available_time_slot',
    'domain_keyword',
    'translation_type',
    'direction',
    'quality_score',
    'contact_keyword',
    'gender',
    'nationality'
  ]
  const textAndSelectCount = countedKeys.reduce(
    (count, key) => count + (String(advancedFilters[key] || '').trim() ? 1 : 0),
    0
  )
  const booleanCount = ['can_cloud_edit', 'can_revision'].reduce(
    (count, key) => count + (advancedFilters[key] !== null ? 1 : 0),
    0
  )
  const rangeCount = [
    ['default_priority_min', 'default_priority_max'],
    ['daily_word_capacity_min', 'daily_word_capacity_max']
  ].reduce(
    (count, keys) => count + (keys.some((key) => advancedFilters[key] !== null) ? 1 : 0),
    0
  )
  return textAndSelectCount + booleanCount + rangeCount + (advancedFilters.stale_only ? 1 : 0)
})

let searchTimer = null
let translatorsRequestController = null
let translatorsRequestId = 0

const statusLabel = (s) => ({ active: '活跃', standby: '备用', inactive: '停用' }[s] || '备用')
const statusTagType = (s) => ({ active: 'success', standby: 'info', inactive: 'danger' }[s] || 'info')

const domainTagType = (level) => {
  if (!level) return 'info'
  if (level.includes('擅长')) return 'success'
  if (level.includes('审改')) return 'warning'
  return 'info'
}

const displayValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  if (Array.isArray(value)) {
    if (!value.length) return '-'
    return value.map((item) => {
      if (typeof item === 'object') {
        return [item.domain, item.level].filter(Boolean).join(':')
      }
      return String(item)
    }).join('；')
  }
  return String(value)
}

const detailItems = [
  { label: '译员编号', key: 'translator_code' },
  { label: '姓名', key: 'translator_name' },
  { label: '状态', key: 'status', type: 'status' },
  { label: '合作形式', key: 'cooperation_type' },
  { label: '语种', key: 'languages' },
  { label: '翻译类型', key: 'translation_type' },
  { label: '口译水平', key: 'interpretation_level' },
  { label: '方向', key: 'direction' },
  { label: '质量评分', key: 'quality_score' },
  { label: '默认优先级', key: 'default_priority' },
  { label: '领域能力', key: 'domain_skills', span: 2 },
  { label: '可接稿时段', key: 'available_time_slot' },
  { label: '日接单数', key: 'daily_accept_count' },
  { label: '每小时时速', key: 'hourly_speed' },
  { label: '每日字数产能', key: 'daily_word_capacity' },
  { label: '支持云编辑', key: 'can_cloud_edit', type: 'boolean' },
  { label: '支持审校', key: 'can_revision', type: 'boolean' },
  { label: '逾期次数', key: 'overdue_count' },
  { label: '排期备注', key: 'schedule_remarks', span: 2 },
  { label: '联系电话1', key: 'phone' },
  { label: '联系电话2', key: 'phone2' },
  { label: '邮箱1', key: 'email1' },
  { label: '邮箱2', key: 'email2' },
  { label: '其他联系方式', key: 'other_contact' },
  { label: '联系信息', key: 'contact_info' },
  { label: '性别', key: 'gender' },
  { label: '国籍', key: 'nationality' },
  { label: '民族', key: 'ethnicity' },
  { label: '身高', key: 'height' },
  { label: '形象', key: 'appearance' },
  { label: '简历路径', key: 'resume_path', span: 2 },
  { label: '初次沟通时间', key: 'first_contact_date', type: 'datetime' },
  { label: '总评', key: 'overall_rating', span: 2 },
  { label: '备注', key: 'remarks', span: 2 },
  { label: '排期更新时间', key: 'availability_updated_at', type: 'datetime' },
  { label: '创建时间', key: 'created_at', type: 'datetime' },
  { label: '更新时间', key: 'updated_at', type: 'datetime' }
]

const formatBooleanValue = (value) => {
  if (value === null || value === undefined) return '-'
  return value ? '是' : '否'
}

const DetailPopover = defineComponent({
  name: 'DetailPopover',
  props: {
    row: { type: Object, required: true },
    title: { type: String, default: '详情' },
    items: { type: Array, default: () => [] }
  },
  setup(props) {
    return () => h(
      ElPopover,
      { placement: 'left', width: 760, trigger: 'click', title: props.title },
      {
        reference: () => h(ElButton, { type: 'info', size: 'small', link: true }, () => '查看详情'),
        default: () => h(
          'div',
          { class: 'detail-popover' },
          h(
            ElDescriptions,
            { column: 2, border: true, size: 'small' },
            () => props.items.map((item) => h(
              ElDescriptionsItem,
              { key: item.key, label: item.label, span: item.span || 1 },
              () => {
                const value = props.row[item.key]
                if (item.type === 'status') {
                  return h(ElTag, { type: statusTagType(value) }, () => statusLabel(value))
                }
                if (item.type === 'boolean') {
                  return h('span', { class: 'detail-value' }, value === null || value === undefined ? '-' : (value ? '是' : '否'))
                }
                if (item.type === 'datetime') {
                  return h('span', { class: 'detail-value' }, formatDetailDatetime(value))
                }
                return h('span', { class: 'detail-value' }, displayValue(value))
              }
            ))
          )
        )
      }
    )
  }
})

const buildFilterParams = () => {
  const params = {}
  const trimFields = [
    'translator_code',
    'translator_name',
    'languages',
    'available_time_slot',
    'domain_keyword',
    'contact_keyword',
    'quality_score',
    'gender',
    'nationality'
  ]
  trimFields.forEach(f => {
    const source = f === 'translator_name' ? searchForm : advancedFilters
    if (source[f]?.trim()) params[f] = source[f].trim()
  })
  const selectFields = ['cooperation_type', 'translation_type', 'direction']
  selectFields.forEach(f => {
    if (advancedFilters[f]) params[f] = advancedFilters[f]
  })
  if (searchForm.status) params.status = searchForm.status
  const nullableFields = [
    'can_cloud_edit',
    'can_revision',
    'default_priority_min',
    'default_priority_max',
    'daily_word_capacity_min',
    'daily_word_capacity_max'
  ]
  nullableFields.forEach((field) => {
    if (advancedFilters[field] !== null) params[field] = advancedFilters[field]
  })
  if (advancedFilters.stale_only) {
    params.stale_only = true
    params.stale_days = advancedFilters.stale_days
  }
  return params
}

const handleSearch = () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  pagination.page = 1
  fetchData()
}

const handleTextFilterInput = (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!value) {
    handleSearch()
    return
  }
  searchTimer = setTimeout(handleSearch, 400)
}

const handleSelectionFilterChange = () => {
  handleSearch()
}

const handleStaleDaysChange = () => {
  if (advancedFilters.stale_only) handleSearch()
}

const handleReset = () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  Object.assign(searchForm, defaultSearchForm)
  Object.assign(advancedFilters, createDefaultAdvancedFilters())
  pagination.page = 1
  fetchData()
}

const clearAdvancedFilters = () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  Object.assign(advancedFilters, createDefaultAdvancedFilters())
  pagination.page = 1
  fetchData()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchData()
}

const handleSortChange = ({ prop, order }) => {
  if (!prop) return
  const sorted = [...tableData.value]
  const normalizeSortValue = (value) => {
    if (value === null || value === undefined || value === '') return null
    if (typeof value === 'number') return value
    const parsedDate = Date.parse(value)
    if (!Number.isNaN(parsedDate)) return parsedDate
    const parsedNumber = Number(value)
    if (!Number.isNaN(parsedNumber) && String(value).trim() !== '') return parsedNumber
    return String(value)
  }
  sorted.sort((a, b) => {
    const va = normalizeSortValue(a[prop])
    const vb = normalizeSortValue(b[prop])
    if (va === null && vb === null) return 0
    if (va === null) return 1
    if (vb === null) return -1
    if (typeof va === 'string' || typeof vb === 'string') {
      const result = String(va).localeCompare(String(vb), 'zh-CN')
      return order === 'ascending' ? result : -result
    }
    return order === 'ascending' ? va - vb : vb - va
  })
  tableData.value = sorted
}

const defaultForm = {
  id: null,
  translator_code: '',
  translator_name: '',
  cooperation_type: '',
  contact_info: '',
  translation_type: '',
  interpretation_level: '',
  quality_score: '',
  direction: '',
  default_priority: 0,
  schedule_remarks: '',
  languages: '',
  gender: '',
  height: '',
  appearance: '',
  nationality: '',
  ethnicity: '',
  phone: '',
  phone2: '',
  email1: '',
  email2: '',
  resume_path: '',
  other_contact: '',
  overdue_count: 0,
  overall_rating: '',
  first_contact_date: null,
  remarks: '',
  status: 'standby',
  available_time_slot: '',
  daily_accept_count: null,
  hourly_speed: null,
  daily_word_capacity: null,
  can_cloud_edit: null,
  can_revision: null,
  domain_skills: [],
}

const form = reactive({ ...defaultForm })
const rules = {
  translator_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email1: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }],
  email2: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }]
}

const addDomainSkill = () => {
  form.domain_skills.push({ domain: '', level: '' })
}

const removeDomainSkill = (index) => {
  form.domain_skills.splice(index, 1)
}

const fetchData = async () => {
  translatorsRequestController?.abort()
  translatorsRequestController = new AbortController()
  const requestId = ++translatorsRequestId
  loading.value = true
  try {
    const filterParams = buildFilterParams()
    const params = {
      ...filterParams,
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit
    }
    const [res, countRes] = await Promise.all([
      translatorApi.getTranslators(params, { signal: translatorsRequestController.signal }),
      translatorApi.getTranslatorCount(filterParams, { signal: translatorsRequestController.signal })
    ])
    if (requestId !== translatorsRequestId) return
    tableData.value = res || []
    pagination.total = countRes?.total || 0
  } catch (error) {
    if (error?.code === 'ERR_CANCELED' || requestId !== translatorsRequestId) return
    ElMessage.error(error?.detail || '网络异常，译员列表未刷新，请检查网络后重试')
  } finally {
    if (requestId === translatorsRequestId) loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增译员'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑译员'
  const fields = Object.keys(defaultForm)
  const data = {}
  for (const key of fields) {
    if (['overdue_count', 'default_priority', 'daily_accept_count', 'hourly_speed', 'daily_word_capacity'].includes(key)) {
      data[key] = row[key] ?? (key === 'overdue_count' || key === 'default_priority' ? 0 : null)
    } else if (key === 'domain_skills') {
      data[key] = JSON.parse(JSON.stringify(row[key] || []))
    } else if (key === 'can_cloud_edit' || key === 'can_revision') {
      data[key] = row[key] ?? null
    } else if (key === 'first_contact_date') {
      data[key] = row[key] || null
    } else {
      data[key] = row[key] ?? ''
    }
  }
  data.id = row.id
  Object.assign(form, data)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该译员吗？', '提示', { type: 'warning' })
    await translatorApi.deleteTranslator(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const submitData = { ...form }
        submitData.domain_skills = (form.domain_skills || []).filter(s => s.domain)
        delete submitData.id
        // 排期更新时间由排期维护流程管理，不应随基础资料编辑回传。
        delete submitData.availability_updated_at
        if (!submitData.first_contact_date) submitData.first_contact_date = null
        if (form.id) {
          await translatorApi.updateTranslator(form.id, submitData)
          ElMessage.success('更新成功')
        } else {
          await translatorApi.createTranslator(submitData)
          ElMessage.success('创建成功')
        }
        dialogVisible.value = false
        fetchData()
      } catch (error) {
        ElMessage.error(error.detail || '操作失败')
      }
    }
  })
}

const resetForm = () => {
  const clean = { ...defaultForm, domain_skills: [] }
  Object.assign(form, clean)
  formRef.value?.resetFields()
}

const demoImportVisible = ref(false)
const demoImportLoading = ref(false)
const demoPreviewLoading = ref(false)
const demoImportInput = ref(null)
const demoImportFile = ref(null)
const demoImportFileName = ref('')
const demoImportOverwrite = ref(true)
const demoImportPreview = ref(null)
const demoImportResult = ref(null)

const handleDemoFileChange = (event) => {
  const [file] = event.target.files || []
  demoImportFile.value = file || null
  demoImportFileName.value = file?.name || ''
  demoImportPreview.value = null
  demoImportResult.value = null
}

const resetDemoImportState = () => {
  demoImportFile.value = null
  demoImportFileName.value = ''
  demoImportPreview.value = null
  demoImportResult.value = null
  demoImportOverwrite.value = true
  if (demoImportInput.value) {
    demoImportInput.value.value = ''
  }
}

const closeDemoImportDialog = () => {
  demoImportVisible.value = false
}

const previewDemoImport = async () => {
  if (!demoImportFile.value) {
    ElMessage.warning('请先选择 Excel 文件')
    return
  }
  demoPreviewLoading.value = true
  try {
    demoImportPreview.value = await scheduleApi.previewTranslatorScheduleDemo(demoImportFile.value)
    demoImportResult.value = null
    ElMessage.success('预览已生成')
  } catch (error) {
    ElMessage.error(error.detail || '预览失败')
  } finally {
    demoPreviewLoading.value = false
  }
}

const submitDemoImport = async () => {
  if (!demoImportPreview.value?.preview_items?.length) {
    ElMessage.warning('请先生成预览')
    return
  }
  demoImportLoading.value = true
  try {
    demoImportResult.value = await scheduleApi.importTranslatorScheduleDemo(
      demoImportFile.value,
      demoImportOverwrite.value
    )
    ElMessage.success('Demo 导入完成')
  } catch (error) {
    ElMessage.error(error.detail || '导入失败')
  } finally {
    demoImportLoading.value = false
  }
}

onMounted(() => { fetchData() })

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  translatorsRequestController?.abort()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.search-area {
  margin-bottom: 16px;
}
.search-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
  margin-bottom: 0;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}
.search-form :deep(.el-form-item) {
  margin: 0;
}
.search-form :deep(.el-form-item:last-child) {
  margin-left: auto;
}
.advanced-filter-badge {
  margin-left: 6px;
  vertical-align: middle;
}
.advanced-filter-title {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}
.advanced-filter-form :deep(.el-form-item) {
  margin-bottom: 16px;
}
.advanced-filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.stale-filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stale-filter-row .el-input-number {
  width: 110px;
}
.stale-days-unit {
  color: var(--el-text-color-secondary);
}
.number-range-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.number-range-filter .el-input-number {
  width: calc((100% - 30px) / 2);
}
:global(.translator-advanced-filter-popper) {
  width: min(760px, calc(100vw - 32px)) !important;
  max-width: calc(100vw - 32px);
}
:global(.translator-advanced-filter-popper .advanced-filter-panel) {
  max-height: min(560px, calc(100vh - 120px));
  overflow-y: auto;
  padding-right: 4px;
}
.detail-popover {
  max-height: 560px;
  overflow-y: auto;
}
.detail-value {
  color: var(--el-text-color-regular);
  word-break: break-all;
  white-space: pre-wrap;
}
.form-section-title {
  margin: 8px 0 14px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 600;
}
.domain-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
.text-muted {
  color: var(--el-text-color-placeholder);
}
.text-stale {
  color: var(--el-color-danger);
  font-weight: 500;
}
.domain-skills-editor {
  padding: 0 20px;
}
:global(.translator-dialog) {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  margin-bottom: 0;
  overflow: hidden;
  border-radius: 10px;
}
:global(.translator-dialog .el-dialog__header) {
  flex: none;
  margin-right: 0;
  padding: 18px 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
:global(.translator-dialog .el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 4px;
}
:global(.translator-dialog .el-dialog__footer) {
  flex: none;
  padding: 14px 24px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  box-shadow: 0 -4px 12px rgb(0 0 0 / 4%);
}
@media (max-width: 768px) {
  .search-form :deep(.el-form-item),
  .search-form :deep(.el-form-item__content),
  .search-form :deep(.el-input),
  .search-form :deep(.el-select) {
    width: 100%;
  }

  .search-form :deep(.el-form-item:last-child) {
    margin-left: 0;
  }

  :global(.translator-dialog .el-col-8) {
    flex: 0 0 100%;
    max-width: 100%;
  }
  :global(.translator-dialog .el-dialog__body) {
    padding: 16px 16px 4px;
  }
}
.demo-import-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.demo-import-tip {
  margin: 0;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.demo-import-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.demo-import-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.demo-preview-summary {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.demo-file-name {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.demo-unmatched {
  margin-top: 8px;
  color: var(--el-color-warning-dark-2);
}
</style>
