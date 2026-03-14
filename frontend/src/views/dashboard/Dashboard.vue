<template>
  <div class="dashboard-page">
    <section class="hero">
      <div>
        <p class="eyebrow">System Overview</p>
        <h1>Dashboard</h1>
        <p class="hero-copy">A quick view of workload, delivery pressure, and finance coverage.</p>
      </div>
      <el-button type="primary" @click="refreshDashboard">Refresh</el-button>
    </section>

    <section class="stats-grid">
      <article class="stat-card">
        <span>Projects</span>
        <strong>{{ stats.totalProjects }}</strong>
        <small>{{ stats.inProgressProjects }} in progress</small>
      </article>
      <article class="stat-card accent-warning">
        <span>Due Soon</span>
        <strong>{{ stats.dueSoonProjects }}</strong>
        <small>{{ stats.overdueProjects }} overdue</small>
      </article>
      <article class="stat-card accent-success">
        <span>Finance Records</span>
        <strong>{{ stats.financeRecords }}</strong>
        <small>{{ stats.unissuedInvoices }} unissued invoices</small>
      </article>
      <article class="stat-card accent-info">
        <span>My Tasks</span>
        <strong>{{ stats.myTasks }}</strong>
        <small>{{ stats.myUrgentTasks }} urgent now</small>
      </article>
    </section>

    <section class="content-grid">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>Upcoming Deadlines</span>
            <el-tag v-if="deadlineProjects.length" type="warning" size="small">{{ deadlineProjects.length }}</el-tag>
          </div>
        </template>
        <el-table v-if="deadlineProjects.length" :data="deadlineProjects" size="small" border>
          <el-table-column prop="orderNo" label="Order No" width="170" />
          <el-table-column prop="projectName" label="Project" min-width="220" show-overflow-tooltip />
          <el-table-column prop="clientShortName" label="Client" width="140" show-overflow-tooltip />
          <el-table-column label="Deadline" width="170">
            <template #default="{ row }">{{ formatDateTime(row.customerDeadlineTime) }}</template>
          </el-table-column>
          <el-table-column label="State" width="110">
            <template #default="{ row }">
              <el-tag :type="isOverdue(row.customerDeadlineTime) ? 'danger' : 'warning'" size="small">{{ isOverdue(row.customerDeadlineTime) ? 'Overdue' : 'Due Soon' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="No urgent deadlines" />
      </el-card>

      <el-card>
        <template #header>
          <div class="card-header">
            <span>My Attention Queue</span>
            <el-tag v-if="myAttentionTasks.length" type="danger" size="small">{{ myAttentionTasks.length }}</el-tag>
          </div>
        </template>
        <el-table v-if="myAttentionTasks.length" :data="myAttentionTasks" size="small" border>
          <el-table-column prop="order_no" label="Order No" width="170" />
          <el-table-column prop="project_name" label="Project" min-width="220" show-overflow-tooltip />
          <el-table-column prop="current_stage_key" label="Stage" width="150" />
          <el-table-column label="Deadline" width="170">
            <template #default="{ row }">{{ formatDateTime(getTaskDeadline(row)) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="No urgent tasks" />
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getFinanceCount } from '@/api/finance'
import { getProjectCount, getProjects } from '@/api/projects'
import { getMyTasksAPI } from '@/api/workflow'

const stats = reactive({
  totalProjects: 0,
  inProgressProjects: 0,
  dueSoonProjects: 0,
  overdueProjects: 0,
  financeRecords: 0,
  unissuedInvoices: 0,
  myTasks: 0,
  myUrgentTasks: 0,
})

const deadlineProjects = ref([])
const myAttentionTasks = ref([])

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function isOverdue(value) {
  if (!value) return false
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return false
  return date < new Date()
}

function isDueSoon(value) {
  if (!value) return false
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return false
  const now = new Date()
  const next48Hours = new Date(now.getTime() + 48 * 60 * 60 * 1000)
  return date >= now && date <= next48Hours
}

function getTaskDeadline(task) {
  return task?.customer_deadline_time ?? task?.customerDeadlineTime ?? null
}

async function refreshDashboard() {
  const [
    totalProjects,
    inProgressProjects,
    financeRecords,
    unissuedInvoices,
    myTasks,
    activeProjects,
  ] = await Promise.all([
    getProjectCount(),
    getProjectCount({ project_status: 'in_progress' }),
    getFinanceCount(),
    getFinanceCount({ invoice_status: 'unissued' }),
    getMyTasksAPI(),
    getProjects({ skip: 0, limit: 100, project_status: 'in_progress' }),
  ])

  const activeList = Array.isArray(activeProjects) ? activeProjects : []
  const dueSoon = activeList.filter(item => isDueSoon(item.customerDeadlineTime))
  const overdue = activeList.filter(item => isOverdue(item.customerDeadlineTime))
  const taskList = Array.isArray(myTasks) ? myTasks : []
  const attentionTasks = taskList.filter(item => {
    const deadline = getTaskDeadline(item)
    return isOverdue(deadline) || isDueSoon(deadline)
  })

  stats.totalProjects = totalProjects?.total || 0
  stats.inProgressProjects = inProgressProjects?.total || 0
  stats.financeRecords = financeRecords?.total || 0
  stats.unissuedInvoices = unissuedInvoices?.total || 0
  stats.myTasks = taskList.length
  stats.myUrgentTasks = attentionTasks.length
  stats.dueSoonProjects = dueSoon.length
  stats.overdueProjects = overdue.length

  deadlineProjects.value = [...overdue, ...dueSoon]
    .sort((a, b) => new Date(a.customerDeadlineTime || 0) - new Date(b.customerDeadlineTime || 0))
    .slice(0, 8)
  myAttentionTasks.value = attentionTasks.slice(0, 8)
}

onMounted(refreshDashboard)
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  padding: 24px 28px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #60a5fa 100%);
  color: #fff;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.8;
}

.hero h1 {
  margin: 0;
  font-size: 36px;
}

.hero-copy {
  margin: 10px 0 0;
  max-width: 560px;
  color: rgba(255, 255, 255, 0.82);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.stat-card {
  padding: 20px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.stat-card span {
  display: block;
  font-size: 13px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.stat-card strong {
  display: block;
  margin: 10px 0 6px;
  font-size: 32px;
  line-height: 1;
}

.stat-card small {
  color: #4b5563;
}

.accent-warning { border-top: 4px solid #f59e0b; }
.accent-success { border-top: 4px solid #10b981; }
.accent-info { border-top: 4px solid #3b82f6; }

.content-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

@media (max-width: 960px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
