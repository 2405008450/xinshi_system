<template>
  <section class="arrangement-operation-history" v-loading="loading">
    <h4>账号当日操作记录</h4>
    <p class="muted">以下记录属于该账号当天的整体安排，包含各项目及完成状态的变更。</p>
    <el-descriptions :column="2" border size="small">
      <el-descriptions-item label="录入人">{{ cell.operations?.created?.actor_name || '未记录' }}</el-descriptions-item>
      <el-descriptions-item label="录入时间">{{ time(cell.operations?.created?.operated_at) }}</el-descriptions-item>
      <el-descriptions-item label="最近修改人">{{ cell.operations?.edited?.actor_name || '未记录' }}</el-descriptions-item>
      <el-descriptions-item label="最近修改时间">{{ time(cell.operations?.edited?.operated_at) }}</el-descriptions-item>
      <el-descriptions-item label="状态操作人">{{ cell.operations?.status?.actor_name || cell.completed_by_name || '未记录' }}</el-descriptions-item>
      <el-descriptions-item label="状态操作时间">{{ time(cell.operations?.status?.operated_at || cell.completed_at) }}</el-descriptions-item>
    </el-descriptions>
    <el-alert v-if="error" :title="error" type="warning" :closable="false"><el-button link @click="load">重新加载</el-button></el-alert>
    <el-empty v-else-if="!loading && !items.length" description="暂无可核实的操作历史" :image-size="48" />
    <article v-for="event in items" :key="event.id" class="arrangement-operation-event">
      <strong>{{ event.label }}</strong>
      <p>{{ event.actor_name }} · {{ time(event.operated_at) }}<span v-if="event.carried_from"> · 来源日期 {{ event.carried_from }}</span></p>
      <div v-for="change in event.changes" :key="change.field" class="arrangement-operation-change"><b>{{ change.label }}：</b><span>{{ change.before }} → {{ change.after }}</span></div>
    </article>
    <el-pagination v-if="total > size" v-model:current-page="page" :page-size="size" :total="total" small layout="total, prev, pager, next" @current-change="load" />
  </section>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementChineseTime } from '@/utils/resourceArrangements'
const props = defineProps({ day: { type: Object, required: true }, cell: { type: Object, required: true } })
const time = value => value ? arrangementChineseTime(value) : '未记录'
const page = ref(1), size = 20, items = ref([]), total = ref(0), loading = ref(false), error = ref('')
let controller, sequence = 0
async function load() {
  controller?.abort(); controller = new AbortController(); const seq = ++sequence
  loading.value = true; error.value = ''; items.value = []
  try {
    const data = await api.arrangementHistory(props.day.work_date, props.cell.platform_id, { skip: (page.value - 1) * size, limit: size }, controller.signal)
    if (seq === sequence) { items.value = data.items; total.value = data.total }
  } catch (e) { if (seq === sequence && e.code !== 'ERR_CANCELED') error.value = e.message || '操作历史加载失败' }
  finally { if (seq === sequence) loading.value = false }
}
watch(() => [props.day.work_date, props.cell.platform_id, props.day.revision], () => { page.value = 1; total.value = 0; load() }, { immediate: true })
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<style>
.arrangement-operation-history { margin-top: 16px; }
.arrangement-operation-history h4 { margin: 10px 0; }
.arrangement-operation-event { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.arrangement-operation-event p { margin: 4px 0; color: var(--el-text-color-secondary); }
.arrangement-operation-change { white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 4px; }
</style>
