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

      <section v-if="leaveNotes.length" class="section-block info-block">
        <h4 class="section-title">请假/调休</h4>
        <ul>
          <li v-for="(note, i) in leaveNotes" :key="i">{{ note }}</li>
        </ul>
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

const scheduleDate = ref('')
const weekdayLabel = computed(() => {
  if (!scheduleDate.value) return ''
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return days[new Date(scheduleDate.value).getDay()]
})

const shiftTableData = ref([])
const leaveNotes = ref([])

async function loadScheduleForDate(date) {
  try {
    const stored = await getSchedule(date)
    shiftTableData.value = stored.shift_table ?? []
    leaveNotes.value = stored.leave_notes ?? []
  } catch {
    shiftTableData.value = []
    leaveNotes.value = []
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
</style>
