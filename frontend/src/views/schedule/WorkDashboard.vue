<template>
  <el-card>
    <template #header>
      <ScheduleHeader
        title="我的工作台"
        :model-value="scheduleDate"
        :weekday-label="weekdayLabel"
        :show-admin-actions="false"
        :readonly="false"
        @update:model-value="scheduleDate = $event"
        @change="onDateChange"
      />
    </template>

    <div class="dashboard-flow">
      <section class="section-block">
        <h3 class="section-title">我的任务</h3>
        <MyTasksPanel :current-user-name="currentUserName" :tasks-list="workflowTasks" />
      </section>

      <section class="section-block">
        <ShiftTableReadonly :data="shiftTableData" />
      </section>

      <!-- 请假管理（结构化） -->
      <section class="section-block info-block">
        <h4 class="section-title">请假管理（结构化）</h4>
        <div class="leave-filter-row">
          <el-date-picker
            v-model="leaveFilterRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 340px"
          />
          <el-button type="primary" @click="loadLeaveRecords">查询</el-button>
          <el-button @click="leaveFilterRange = []; loadLeaveRecords()">重置</el-button>
        </div>
        <el-table v-if="leaveRecords.length" :data="leaveRecords" border size="small" class="data-table">
          <el-table-column prop="employee_name" label="员工" width="100" />
          <el-table-column label="开始时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.start_date) }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.end_date) }}</template>
          </el-table-column>
          <el-table-column prop="leave_type" label="类型" width="100" />
          <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
        </el-table>
        <el-empty v-else description="暂无结构化请假记录" :image-size="48" />
      </section>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ScheduleHeader from './components/ScheduleHeader.vue'
import MyTasksPanel from './components/MyTasksPanel.vue'
import ShiftTableReadonly from './components/ShiftTableReadonly.vue'
import { getSchedule } from '@/api/schedule'
import { getMyTasksAPI } from '@/api/workflow'
import { getLeaveRecords } from '@/api/leave'

const scheduleDate = ref('')
const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return days[new Date(scheduleDate.value).getDay()]
})

const shiftTableData = ref([])

// 请假管理
const leaveRecords = ref([])
const leaveFilterRange = ref([])

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

async function loadLeaveRecords() {
  const params = {}
  if (leaveFilterRange.value && leaveFilterRange.value.length === 2) {
    params.start_date = leaveFilterRange.value[0]
    params.end_date = leaveFilterRange.value[1]
  }
  try {
    const res = await getLeaveRecords(params)
    leaveRecords.value = Array.isArray(res) ? res : []
  } catch {
    leaveRecords.value = []
  }
}

async function loadScheduleForDate(date) {
  try {
    const stored = await getSchedule(date)
    shiftTableData.value = stored.shift_table ?? []
  } catch {
    shiftTableData.value = []
  }
}

const currentUserName = ref('')
function initCurrentUserName() {
  try {
    currentUserName.value = (localStorage.getItem('user_name') || '').trim()
  } catch {
    currentUserName.value = ''
  }
}

const workflowTasks = ref([])
async function loadMyWorkflowTasks() {
  try {
    const userId = localStorage.getItem('user_id')
    if (!userId) { workflowTasks.value = []; return }
    const tasks = await getMyTasksAPI(userId)
    workflowTasks.value = Array.isArray(tasks) ? tasks : []
  } catch {
    workflowTasks.value = []
  }
}

function onDateChange() {
  loadScheduleForDate(scheduleDate.value)
}

onMounted(() => {
  initCurrentUserName()
  const today = new Date()
  scheduleDate.value = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, '0'),
    String(today.getDate()).padStart(2, '0')
  ].join('-')
  loadScheduleForDate(scheduleDate.value)
  loadMyWorkflowTasks()
  loadLeaveRecords()
})
</script>

<style scoped>
.dashboard-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.section-block {
  margin-bottom: 28px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--el-color-primary-light-7);
}
.info-block {
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.info-block ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.7;
}
.leave-filter-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.data-table {
  margin-bottom: 12px;
}
</style>
