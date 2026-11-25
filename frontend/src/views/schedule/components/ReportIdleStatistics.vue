<template>
  <section class="idle-statistics">
    <div class="idle-statistics-filters">
      <el-radio-group v-model="period" aria-label="空闲时间统计周期" @change="query">
        <el-radio-button value="day">每日</el-radio-button>
        <el-radio-button value="week">每周</el-radio-button>
        <el-radio-button value="month">每月</el-radio-button>
      </el-radio-group>
      <el-date-picker v-model="anchor" :type="period === 'month' ? 'month' : 'date'" value-format="YYYY-MM-DD"
        :clearable="false" aria-label="空闲时间统计日期" @change="query" />
      <el-button @click="load">刷新统计</el-button>
      <span v-if="result">{{ result.date_from }} 至 {{ result.date_to }}</span>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table v-loading="loading" :data="result?.items || []" border empty-text="暂无有权查看的人员">
      <el-table-column prop="name" label="姓名" min-width="120" />
      <el-table-column :label="period === 'day' ? '当日空闲时间' : period === 'week' ? '每周空闲合计' : '每月空闲合计'" min-width="160">
        <template #default="{ row }">
          <strong :class="{ 'idle-danger': period === 'day' && row.idle_minutes > 60 }">
            {{ row.idle_minutes == null ? '暂无已填数据' : row.idle_minutes + ' 分钟' }}
          </strong>
        </template>
      </el-table-column>
      <el-table-column prop="report_count" label="已确认报告数" width="125" />
      <el-table-column label="缺少空闲数据" width="125">
        <template #default="{ row }">{{ row.missing_idle_count }} 份</template>
      </el-table-column>
      <el-table-column label="每日超过60分钟" width="155">
        <template #default="{ row }">
          <el-tag v-if="row.over_limit_days" type="danger">{{ row.over_limit_days }} 天超过60分钟</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="每日明细" min-width="300">
        <template #default="{ row }">
          <div class="idle-daily-details">
            <span v-for="day in row.days" :key="day.date" :class="{ 'idle-danger': day.over_limit }">
              {{ day.date }} · {{ day.idle_minutes == null ? '未填写' : day.idle_minutes + '分钟' }}
              <b v-if="day.over_limit">超过60分钟</b>
            </span>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10,20,50]"
      :total="result?.total || 0" layout="total,sizes,prev,pager,next" @current-change="load" @size-change="query" />
    <p v-if="result" class="idle-basis">{{ result.basis }}</p>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getReportIdleStatistics } from '@/api/tasks'
import { reportBusinessDate } from '@/utils/workReportForm'
import { subscribe } from '@/utils/realtimeSocket'

const props = defineProps({ departmentId: String, keyword: String, senderId: String })
const period = ref('day')
const anchor = ref(reportBusinessDate())
const page = ref(1)
const pageSize = ref(20)
const result = ref(null)
const loading = ref(false)
const error = ref('')
let controller, sequence = 0

async function load() {
  if (!anchor.value) return
  controller?.abort()
  controller = new AbortController()
  const current = ++sequence
  loading.value = true
  error.value = ''
  try {
    const data = await getReportIdleStatistics({
      anchor: anchor.value, period: period.value, department_id: props.departmentId || undefined,
      keyword: props.keyword || undefined, sender_id: props.senderId || undefined,
      page: page.value, page_size: pageSize.value,
    }, { signal: controller.signal })
    if (current === sequence) result.value = data
  } catch (reason) {
    if (current === sequence && reason.code !== 'ERR_CANCELED') {
      result.value = null
      error.value = reason.detail || '读取空闲时间统计失败'
    }
  } finally {
    if (current === sequence) loading.value = false
  }
}
function query() { page.value = 1; return load() }
watch(() => [props.departmentId, props.keyword, props.senderId], query)
const stopUpdates = subscribe('daily_report_updated', load)
onMounted(() => {
  load()
  window.addEventListener('work-report-lunch-changed', load)
  window.addEventListener('focus', load)
})
onBeforeUnmount(() => {
  stopUpdates()
  sequence++
  controller?.abort()
  window.removeEventListener('work-report-lunch-changed', load)
  window.removeEventListener('focus', load)
})
</script>

<style scoped>
.idle-statistics { display: grid; gap: 12px; }
.idle-statistics-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.idle-statistics-filters .el-date-editor { width: 180px; max-width: 100%; }
.idle-danger { color: #b91c1c; font-weight: 700; }
.idle-daily-details { display: flex; flex-wrap: wrap; gap: 6px 16px; max-height: 160px; overflow-y: auto; }
.idle-daily-details span { display: inline-block; }
.idle-basis { margin: 0; color: var(--el-text-color-secondary); font-size: 12px; }
</style>
