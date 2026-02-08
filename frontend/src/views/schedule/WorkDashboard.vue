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
        <MyTasksPanel :current-user-name="currentUserName" :tasks-list="myTasksList" />
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
import { useScheduleData } from './composables/useScheduleData'

const {
  scheduleDate,
  weekdayLabel,
  deptPersonData,
  shiftTableData,
  leaveNotes,
  loadScheduleForDate
} = useScheduleData()

const currentUserName = ref('')
function initCurrentUserName() {
  try {
    currentUserName.value = (localStorage.getItem('user_name') || '').trim()
  } catch {
    currentUserName.value = ''
  }
}

const myTasksList = computed(() => {
  const name = currentUserName.value
  if (!name) return []
  const person = deptPersonData.value.find(
    (p) => p.name === name || p.name.includes(name) || name.includes(p.name)
  )
  if (!person || !person.tasks) return []
  return person.tasks.map((t) => ({
    category: t.category,
    content: t.content,
    projectNo: t.projectNo || '',
    deadline: t.deadline || ''
  }))
})

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
