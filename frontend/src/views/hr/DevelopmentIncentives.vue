<template>
  <el-card v-loading="loading" class="common-page-card" shadow="never">
    <template #header><div class="incentive-header"><h2>开发部门奖励</h2><el-button @click="load">刷新</el-button></div></template>
    <el-alert v-if="error" :title="error" type="error" :closable="false" /><el-alert v-if="!enabled && !loading" title="奖励统计表尚未初始化" type="warning" :closable="false" />
    <p class="incentive-tip">按执行人分别抵消，不跨人员抵消；日期、预定日期或执行人调整后，旧评定金额只保留历史，当前新评定登记后才计入统计。</p>
    <el-descriptions :column="3" border><el-descriptions-item v-for="field in fields" :key="field.key" :label="field.label">{{ totals[field.key] || '0.00' }}</el-descriptions-item></el-descriptions>
    <h3>按执行人汇总</h3><el-table :data="people" border><el-table-column prop="executor_name" label="执行人" min-width="150" /><el-table-column v-for="field in fields" :key="field.key" :prop="field.key" :label="field.label" min-width="130" /><el-table-column prop="pending" label="待登记金额的任务" min-width="150" /></el-table>
    <h3>任务金额明细</h3><el-table :data="tasks" border><el-table-column prop="task_no" label="任务编号" min-width="175" /><el-table-column prop="task_name" label="任务名称" min-width="220" show-overflow-tooltip /><el-table-column prop="executor_name" label="执行人" width="120" /><el-table-column prop="due_on" label="预定完成日期" width="150" /><el-table-column prop="completed_on" label="完成日期" width="150" /><el-table-column label="是否按时完成" width="135"><template #default="{ row }">{{ row.on_time == null ? '待完成' : row.on_time ? '是' : '否' }}</template></el-table-column><el-table-column label="类型" width="130"><template #default="{ row }">{{ row.on_time == null ? '-' : row.on_time ? '给予奖励' : '抵消奖金' }}</template></el-table-column><el-table-column label="当前金额" width="130"><template #default="{ row }">{{ row.incentive?.amount ?? (row.on_time == null ? '-' : '待登记') }}</template></el-table-column><el-table-column label="调整记录" width="120" fixed="right"><template #default="{ row }"><TaskCompletionHistory :task-id="row.task_id" /></template></el-table-column></el-table>
  </el-card>
</template>
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getTechnicalIncentives } from '@/api/technicalIncentives'
import TaskCompletionHistory from '@/views/technology/TaskCompletionHistory.vue'
const people = ref([]), tasks = ref([]), totals = ref({}), loading = ref(false), error = ref(''), enabled = ref(true)
const fields = [{ key: 'reward_total', label: '奖励合计' }, { key: 'deduction_total', label: '抵消奖金合计' }, { key: 'offset_total', label: '已相互抵消' }, { key: 'net_reward', label: '抵消后奖励余额' }, { key: 'net_deduction', label: '待抵消奖金余额' }]
let controller, sequence = 0
async function load() { const current = ++sequence; controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''; try { const value = await getTechnicalIncentives(controller.signal); if (current === sequence) { people.value = value.people; tasks.value = value.tasks; totals.value = value.totals; enabled.value = value.enabled } } catch (e) { if (current === sequence && e.code !== 'ERR_CANCELED') error.value = typeof e.detail === 'string' ? e.detail : '加载奖励统计失败' } finally { if (current === sequence) loading.value = false } }
onMounted(load); onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<style scoped>.incentive-header{display:flex;justify-content:space-between;align-items:center;gap:12px}.incentive-header h2{margin:0;font-size:18px}.incentive-tip{color:var(--el-text-color-secondary);font-size:13px;line-height:1.7}h3{font-size:16px;margin-top:22px}</style>
