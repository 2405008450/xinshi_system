<template>
  <el-button link type="primary" @click="open">调整记录</el-button>
  <DraggableFormDialog v-model="visible" title="完成日期与奖励调整记录" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body>
    <div v-loading="loading" class="completion-history">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="value"><p><strong>{{ value.task_no }} · {{ value.task_name }}</strong></p><h4>完成日期调整记录</h4><el-empty v-if="!value.changes.length" description="暂无记录" :image-size="50" /><article v-for="change in value.changes" :key="change.id"><strong>{{ change.previous_date || '未填写' }} → {{ change.completed_on || '未填写' }}</strong><p>预定完成日期：{{ change.previous_due_on || '-' }} → {{ change.due_on || '-' }}</p><p>{{ change.reason }}</p><small>{{ change.author_name }}（{{ change.author_username }}） · {{ formatTime(change.created_at) }}</small></article><h4>奖励／抵消奖金记录</h4><el-empty v-if="!value.ledger_history.length" description="暂无金额记录" :image-size="50" /><article v-for="entry in value.ledger_history" :key="entry.id"><el-tag :type="entry.effective ? 'success' : 'info'">{{ entry.effective ? '当前有效' : '历史记录，不计入当前统计' }}</el-tag><p>{{ entry.executor_name }} · {{ entry.kind === 'reward' ? '给予奖励' : '抵消奖金' }} {{ entry.amount }}</p><p v-if="entry.reason">{{ entry.reason }}</p><small>{{ entry.author_name }}（{{ entry.author_username }}） · {{ formatTime(entry.created_at) }}</small></article></template>
    </div>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { ref } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { getTaskCompletion } from '@/api/technicalIncentives'
import { formatBusinessDateTimeMinute as formatTime } from '@/utils/datetime'
const props = defineProps({ taskId: { type: String, required: true } })
const visible = ref(false), loading = ref(false), value = ref(null), error = ref('')
async function open() { visible.value = true; value.value = null; loading.value = true; error.value = ''; try { value.value = await getTaskCompletion(props.taskId) } catch (e) { error.value = typeof e.detail === 'string' ? e.detail : '记录加载失败' } finally { loading.value = false } }
</script>
<style scoped>.completion-history{max-height:65vh;overflow-y:auto;overflow-wrap:anywhere;white-space:pre-wrap}.completion-history article{padding:12px;border:1px solid var(--el-border-color);border-radius:6px;margin:10px 0}.completion-history small{color:var(--el-text-color-secondary)}</style>
