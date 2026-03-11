<template>
  <div class="section-block">
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
      <p v-if="currentUserName" class="section-desc" style="margin-bottom: 0;">当前用户：<strong>{{ currentUserName }}</strong></p>
      
      <el-form v-if="tasksList.length" :inline="true" :model="searchForm" size="small" style="margin-bottom: -18px;">
        <el-form-item label="客户简称">
          <el-input v-model="searchForm.client_short_name" placeholder="支持模糊搜索" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="语言对">
          <el-input v-model="searchForm.language_pair" placeholder="支持模糊搜索" clearable style="width: 140px" />
        </el-form-item>
      </el-form>
    </div>

    <div class="tasks-panel">
      <div class="panel-header" @click="panelExpanded = !panelExpanded">
        <span class="panel-title">
          紧急任务
          <el-tag v-if="urgentTasks.length" type="danger" size="small">{{ urgentTasks.length }}</el-tag>
        </span>
        <el-icon class="expand-icon" :class="{ expanded: panelExpanded }">
          <ArrowDown />
        </el-icon>
      </div>
      <el-collapse-transition>
        <div v-show="panelExpanded" class="panel-content">
          <el-table v-if="urgentTasks.length" :data="urgentTasks" border size="small" class="data-table">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="order_no" label="项目编号" width="180" show-overflow-tooltip />
            <el-table-column prop="client_short_name" label="客户简称" width="120" show-overflow-tooltip />
            <el-table-column prop="language_pair" label="语言对" width="140" show-overflow-tooltip />
            <el-table-column label="客户交稿时间" width="160">
              <template #default="{ row }">
                {{ formatDeadline(getTaskDeadline(row)) }}
              </template>
            </el-table-column>
            <el-table-column prop="current_stage_key" label="当前阶段" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ STAGE_LABELS[row.current_stage_key] || row.current_stage_key }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="difficulty" label="难度" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
                  {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="project_status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="STATUS_TYPE[row.project_status] || ''" size="small" effect="plain">
                  {{ STATUS_LABEL[row.project_status] || row.project_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="$emit('enter-project', row.translation_project_id)">进入</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-tip">暂无当天及次日10点前的紧急任务</div>
        </div>
      </el-collapse-transition>
    </div>

    <div class="tasks-panel">
      <div class="panel-header" @click="otherExpanded = !otherExpanded">
        <span class="panel-title">
          其他任务
          <el-tag v-if="otherTasks.length" size="small">{{ otherTasks.length }}</el-tag>
        </span>
        <el-icon class="expand-icon" :class="{ expanded: otherExpanded }">
          <ArrowDown />
        </el-icon>
      </div>
      <el-collapse-transition>
        <div v-show="otherExpanded" class="panel-content">
          <el-table v-if="otherTasks.length" :data="otherTasks" border size="small" class="data-table">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="order_no" label="项目编号" width="180" show-overflow-tooltip />
            <el-table-column prop="client_short_name" label="客户简称" width="120" show-overflow-tooltip />
            <el-table-column prop="language_pair" label="语言对" width="140" show-overflow-tooltip />
            <el-table-column label="客户交稿时间" width="160">
              <template #default="{ row }">
                {{ formatDeadline(getTaskDeadline(row)) }}
              </template>
            </el-table-column>
            <el-table-column prop="current_stage_key" label="当前阶段" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ STAGE_LABELS[row.current_stage_key] || row.current_stage_key }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="difficulty" label="难度" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.difficulty" :type="DIFFICULTY_TYPE[row.difficulty] || ''" size="small" effect="plain">
                  {{ DIFFICULTY_LABEL[row.difficulty] || row.difficulty }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="project_status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="STATUS_TYPE[row.project_status] || ''" size="small" effect="plain">
                  {{ STATUS_LABEL[row.project_status] || row.project_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button v-if="row.translation_project_id" type="primary" link size="small" @click="$emit('enter-project', row.translation_project_id)">进入</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-tip">暂无其他任务</div>
        </div>
      </el-collapse-transition>
    </div>

    <div v-if="currentUserName && !tasksList.length" class="info-block">
      <p>暂无待处理的工作流任务。</p>
    </div>
    <el-empty v-else-if="!currentUserName" description="请先登录，登录账号将用于匹配「我的任务」" />
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'

const STAGE_LABELS = {
  reception: '客户专员',
  layout_assign: '排版指派',
  project_manager: '项目经理',
  project_specialist: '项目专员',
  project_assistant: '项目助理',
  review: '译审',
  special_qc: '专检',
  layout: '排版',
  completed: '完成'
}

const DIFFICULTY_LABEL = { simple: '简单', normal: '普通', complex: '复杂' }
const DIFFICULTY_TYPE = { simple: 'success', normal: '', complex: 'danger' }
const STATUS_LABEL = { pending: '待处理', in_progress: '进行中', completed: '已完成', paused: '暂停' }
const STATUS_TYPE = { pending: 'info', in_progress: '', completed: 'success', paused: 'warning' }

const props = defineProps({
  currentUserName: { type: String, default: '' },
  tasksList: { type: Array, default: () => [] },
  /** 参考日期 YYYY-MM-DD，用于判定「当天及次日10点前」；不传则用当前真实日期 */
  referenceDate: { type: String, default: '' }
})

defineEmits(['enter-project'])

const panelExpanded = ref(true)
const otherExpanded = ref(true)

const searchForm = reactive({
  client_short_name: '',
  language_pair: ''
})

function formatDeadline(timeStr) {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  if (isNaN(d.getTime())) return timeStr
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

/** 从任务对象取客户交稿时间（兼容接口 snake_case / camelCase） */
function getTaskDeadline(task) {
  return task?.customer_deadline_time ?? task?.customerDeadlineTime ?? null
}

/**
 * 判定是否为紧急任务：客户交稿时间在「参考日当天 00:00」到「参考日次日 10:00」之间。
 * @param {string|null} deadlineTime - ISO 或可解析的日期时间字符串
 * @param {string} [refDateStr] - 参考日期 YYYY-MM-DD，不传则用当前日期
 */
function isUrgentTask(deadlineTime, refDateStr) {
  if (!deadlineTime) return false
  const deadline = new Date(deadlineTime)
  if (isNaN(deadline.getTime())) return false

  const ref = refDateStr && refDateStr.trim() ? new Date(refDateStr + 'T00:00:00') : new Date()
  const today = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate())
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)

  const deadlineCutoff = new Date(tomorrow)
  deadlineCutoff.setHours(10, 0, 0, 0)

  return deadline >= today && deadline <= deadlineCutoff
}

const urgentTasks = computed(() => {
  const ref = (props.referenceDate || '').trim() || null
  let list = props.tasksList.filter(task => isUrgentTask(getTaskDeadline(task), ref))
  
  if (searchForm.client_short_name) {
    list = list.filter(t => t.client_short_name && t.client_short_name.includes(searchForm.client_short_name))
  }
  if (searchForm.language_pair) {
    list = list.filter(t => t.language_pair && t.language_pair.includes(searchForm.language_pair))
  }
  return list
})

const otherTasks = computed(() => {
  const ref = (props.referenceDate || '').trim() || null
  let list = props.tasksList.filter(task => !isUrgentTask(getTaskDeadline(task), ref))
  
  if (searchForm.client_short_name) {
    list = list.filter(t => t.client_short_name && t.client_short_name.includes(searchForm.client_short_name))
  }
  if (searchForm.language_pair) {
    list = list.filter(t => t.language_pair && t.language_pair.includes(searchForm.language_pair))
  }
  return list
})
</script>

<style scoped>
.section-block { margin-bottom: 28px; }
.section-desc { margin: 0 0 8px 0; line-height: 1.6; color: var(--el-text-color-regular); }
.data-table { margin-bottom: 12px; }
.info-block {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.info-block p { margin: 0; font-size: 13px; color: var(--el-text-color-regular); }

.tasks-panel {
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  cursor: pointer;
  user-select: none;
}
.panel-header:hover {
  background: var(--el-fill-color);
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}
.expand-icon {
  transition: transform 0.3s;
}
.expand-icon.expanded {
  transform: rotate(180deg);
}
.panel-content {
  padding: 12px;
}
.empty-tip {
  padding: 20px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
