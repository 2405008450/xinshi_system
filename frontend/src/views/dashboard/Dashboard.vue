<template>
  <div class="dashboard-page">
    <section class="hero">
      <div>
        <p class="eyebrow">&#x7CFB;&#x7EDF;&#x6982;&#x89C8;</p>
        <h1>&#x6570;&#x636E;&#x770B;&#x677F;</h1>
        <p class="hero-copy">&#x5FEB;&#x901F;&#x67E5;&#x770B;&#x5F53;&#x524D;&#x5DE5;&#x4F5C;&#x8D1F;&#x8377;&#x3001;&#x4EA4;&#x4ED8;&#x538B;&#x529B;&#x548C;&#x8D22;&#x52A1;&#x8986;&#x76D6;&#x60C5;&#x51B5;&#x3002;</p>
      </div>
      <el-button type="primary" @click="refreshDashboard">&#x5237;&#x65B0;</el-button>
    </section>

    <section class="stats-grid">
      <article class="stat-card">
        <span>&#x9879;&#x76EE;&#x603B;&#x6570;</span>
        <strong>{{ stats.totalProjects }}</strong>
        <small>{{ stats.inProgressProjects }} &#x4E2A;&#x8FDB;&#x884C;&#x4E2D;</small>
      </article>
      <article class="stat-card accent-warning">
        <span>&#x5373;&#x5C06;&#x5230;&#x671F;</span>
        <strong>{{ stats.dueSoonProjects }}</strong>
        <small>{{ stats.overdueProjects }} &#x4E2A;&#x5DF2;&#x903E;&#x671F;</small>
      </article>
      <article class="stat-card accent-success">
        <span>&#x8D22;&#x52A1;&#x8BB0;&#x5F55;</span>
        <strong>{{ stats.financeRecords }}</strong>
        <small>{{ stats.unissuedInvoices }} &#x6761;&#x672A;&#x5F00;&#x7968;</small>
      </article>
      <article class="stat-card accent-info">
        <span>&#x6211;&#x7684;&#x4EFB;&#x52A1;</span>
        <strong>{{ stats.myTasks }}</strong>
        <small>{{ stats.myUrgentTasks }} &#x9879;&#x5F53;&#x524D;&#x7D27;&#x6025;</small>
      </article>
    </section>

    <section class="content-grid">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>&#x4E34;&#x671F;&#x9879;&#x76EE;</span>
            <el-tag v-if="deadlineProjects.length" type="warning" size="small">{{ deadlineProjects.length }}</el-tag>
          </div>
        </template>
        <el-table v-if="deadlineProjects.length" :data="deadlineProjects" size="small" border>
          <el-table-column prop="orderNo" label="&#x8BA2;&#x5355;&#x53F7;" width="170" />
          <el-table-column prop="projectName" label="&#x9879;&#x76EE;&#x540D;&#x79F0;" min-width="220" show-overflow-tooltip />
          <el-table-column prop="clientShortName" label="&#x5BA2;&#x6237;" width="140" show-overflow-tooltip />
          <el-table-column label="&#x622A;&#x6B62;&#x65F6;&#x95F4;" width="170">
            <template #default="{ row }">{{ formatDateTime(row.customerDeadlineTime) }}</template>
          </el-table-column>
          <el-table-column label="&#x72B6;&#x6001;" width="110">
            <template #default="{ row }">
              <el-tag :type="isOverdue(row.customerDeadlineTime) ? 'danger' : 'warning'" size="small">{{ isOverdue(row.customerDeadlineTime) ? '已逾期' : '即将到期' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="&#x6682;&#x65E0;&#x7D27;&#x6025;&#x622A;&#x6B62;&#x9879;&#x76EE;" />
      </el-card>

      <el-card>
        <template #header>
          <div class="card-header">
            <span>&#x6211;&#x7684;&#x5173;&#x6CE8;&#x961F;&#x5217;</span>
            <el-tag v-if="myAttentionTasks.length" type="danger" size="small">{{ myAttentionTasks.length }}</el-tag>
          </div>
        </template>
        <el-table v-if="myAttentionTasks.length" :data="myAttentionTasks" size="small" border>
          <el-table-column prop="order_no" label="&#x8BA2;&#x5355;&#x53F7;" width="170" />
          <el-table-column prop="project_name" label="&#x9879;&#x76EE;&#x540D;&#x79F0;" min-width="220" show-overflow-tooltip />
          <el-table-column prop="current_stage_key" label="&#x5F53;&#x524D;&#x9636;&#x6BB5;" width="150" />
          <el-table-column label="&#x622A;&#x6B62;&#x65F6;&#x95F4;" width="170">
            <template #default="{ row }">{{ formatDateTime(getTaskDeadline(row)) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="&#x6682;&#x65E0;&#x7D27;&#x6025;&#x4EFB;&#x52A1;" />
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
