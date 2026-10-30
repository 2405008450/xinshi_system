<template>
  <el-button link type="primary" :disabled="!taskId" @click="open">{{ label || (kind === 'progress' ? '查看每日进度' : '查看任务详情') }}</el-button>
  <DraggableFormDialog v-model="visible" :title="kind === 'progress' ? '技术任务每日进度' : '技术开发任务详情'" width="min(800px, calc(100vw - 32px))" top="5vh" append-to-body>
    <div v-loading="loading" class="technical-reference-body">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="task">
        <p><strong>{{ task.task_no }} · {{ task.name }}</strong></p>
        <template v-if="kind === 'progress'">
          <el-progress :percentage="task.progress" />
          <el-empty v-if="!days.length" description="暂无进度修改记录" :image-size="60" />
          <section v-for="day in days" :key="day.date" class="technical-progress-day"><h4>{{ day.date }}</h4><article v-for="record in day.records" :key="record.id"><div><strong>{{ record.previous_percentage }}% → {{ record.percentage }}%</strong> · {{ record.author_name }} · {{ formatTime(record.created_at) }}</div><p>{{ record.content || '未填写具体进度' }}</p><p v-if="record.reason">修改原因：{{ record.reason }}</p></article></section>
        </template>
        <el-descriptions v-else :column="2" border size="small"><el-descriptions-item label="任务编号">{{ task.task_no }}</el-descriptions-item><el-descriptions-item label="任务名称">{{ task.name }}</el-descriptions-item><el-descriptions-item label="具体任务" :span="2">{{ task.content || '-' }}</el-descriptions-item><el-descriptions-item label="安排人">{{ task.arranger_name }}</el-descriptions-item><el-descriptions-item label="执行人">{{ task.executor_name }}</el-descriptions-item><el-descriptions-item label="预定完成时间">{{ formatTime(task.due_at) }}</el-descriptions-item><el-descriptions-item label="具体进度">{{ task.progress }}%</el-descriptions-item><el-descriptions-item label="反馈后调整" :span="2">{{ task.adjustment || '-' }}</el-descriptions-item><el-descriptions-item label="备注" :span="2">{{ task.notes || '-' }}</el-descriptions-item></el-descriptions>
      </template>
    </div>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, ref } from 'vue'
import DraggableFormDialog from './DraggableFormDialog.vue'
import { getDevelopmentTask } from '@/api/technicalDevelopment'
import { businessDateTimeInputValue, formatBusinessDateTimeMinute as formatTime } from '@/utils/datetime'
const props = defineProps({ taskId: { type: String, required: true }, label: { type: String, default: '' }, kind: { type: String, default: 'details' } })
const visible = ref(false), loading = ref(false), error = ref(''), task = ref(null)
let sequence = 0
async function open() {
  const current = ++sequence
  visible.value = true; task.value = null; loading.value = true; error.value = ''
  try { const value = await getDevelopmentTask(props.taskId); if (current === sequence) task.value = value }
  catch (e) { if (current === sequence) error.value = typeof e.detail === 'string' ? e.detail : '任务记录加载失败' }
  finally { if (current === sequence) loading.value = false }
}
const days = computed(() => {
  const groups = new Map()
  for (const record of task.value?.progress_history || []) { const day = businessDateTimeInputValue(record.created_at).slice(0, 10); if (!groups.has(day)) groups.set(day, []); groups.get(day).push(record) }
  return [...groups].sort(([a], [b]) => b.localeCompare(a)).map(([date, records]) => ({ date, records }))
})
</script>
<style scoped>
.technical-reference-body{max-height:65vh;overflow-y:auto;white-space:pre-wrap;overflow-wrap:anywhere}.technical-progress-day article{padding:12px;border:1px solid var(--el-border-color);border-radius:6px;margin-bottom:10px}.technical-progress-day article>div{font-size:13px;color:var(--el-text-color-secondary)}
</style>
