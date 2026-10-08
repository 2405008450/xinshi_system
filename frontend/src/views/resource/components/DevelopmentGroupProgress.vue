<template>
  <div class="development-group-progress">
    <el-dropdown v-if="editable" trigger="click" :disabled="saving" @command="chooseStatus">
      <el-button link type="primary" :loading="saving" :aria-label="`${row.full_name}的${label}状态`">{{ status }}<span class="group-arrow">▾</span></el-button>
      <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="value in progressStatuses(channel)" :key="value" :command="value" :disabled="value === status">{{ value }}</el-dropdown-item></el-dropdown-menu></template>
    </el-dropdown>
    <span v-else>{{ status }}</span>
    <small v-if="progress">{{ date(progress.action_date) }} · {{ progress.operator_name || '-' }}</small>
    <el-popover trigger="click" placement="left" :width="760" :title="`${row.full_name} · ${label}操作历史`" popper-class="development-group-history" @show="loadHistory">
      <template #reference><el-button link type="primary" size="small">查看历史</el-button></template>
      <div v-loading="historyLoading" class="group-history-body">
        <el-alert v-if="historyError" :title="historyError" type="error" :closable="false" /><el-button v-if="historyError" link type="primary" @click="loadHistory">重试</el-button>
        <el-empty v-else-if="!historyLoading && !history.length && !marker" description="暂无操作记录" :image-size="55" />
        <el-descriptions v-for="action in history" :key="action.id" :column="2" border size="small" class="group-history-record">
          <el-descriptions-item label="状态">{{ groupStatusLabel(action.status, channel) }}</el-descriptions-item>
          <el-descriptions-item label="操作日期">{{ date(action.action_date) }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ action.operator_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="记录时间">{{ time(action.created_at) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions v-if="marker" :column="2" border size="small" class="group-history-record">
          <el-descriptions-item label="历史原表状态">{{ groupStatusLabel(marker.status, channel) }}</el-descriptions-item>
          <el-descriptions-item label="操作日期">{{ date(marker.action_date) }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ marker.operator_name || '原表未填写' }}</el-descriptions-item>
          <el-descriptions-item label="来源">历史导入</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { groupStatusLabel, newDevelopmentId, progressChannels, progressStatuses } from '@/utils/resourceDevelopment'
const props = defineProps({ row: { type: Object, required: true }, channel: { type: String, required: true }, editable: Boolean })
const emit = defineEmits(['saved', 'edit'])
const saving = ref(false), historyLoading = ref(false), detail = ref(null), historyError = ref('')
const label = computed(() => progressChannels[props.channel])
const progress = computed(() => props.row.progress?.[props.channel])
const status = computed(() => groupStatusLabel(progress.value?.status || '未处理', props.channel))
const history = computed(() => (detail.value?.actions || []).filter(action => action.channel === props.channel).slice().reverse())
const marker = computed(() => detail.value?.historical_progress?.[props.channel] || detail.value?.historical_markers?.[props.channel])
const date = value => value ? new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString('zh-CN') : '原表未填写'
const time = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
let controller, sequence = 0
function clearHistory() { controller?.abort(); sequence++; detail.value = null; historyLoading.value = false; historyError.value = '' }
watch(() => [props.row.id, props.row.revision], clearHistory)
async function loadHistory() {
  if (detail.value || historyLoading.value) return
  controller = new AbortController(); const current = ++sequence
  historyLoading.value = true; historyError.value = ''
  try { const data = await api.detail(props.row.id, controller.signal); if (current === sequence) detail.value = data }
  catch (error) { if (current === sequence && !controller.signal.aborted) historyError.value = error.message }
  finally { if (current === sequence) historyLoading.value = false }
}
async function chooseStatus(value) {
  if (saving.value || !props.editable || value === status.value) return
  if (value === '已进群' && !props.row.person_id) { emit('edit', props.row, props.channel, value); return }
  saving.value = true
  try {
    await api.saveGroupAction(props.row.id, { id: newDevelopmentId(), revision: props.row.revision, channel: props.channel, status: value })
    clearHistory(); ElMessage.success(`${label.value}状态已保存`); emit('saved')
  } catch (error) {
    if (error.rawDetail?.code === 'enrollment_required') emit('edit', props.row, props.channel, value)
    else { ElMessage.error(error.message); if (error.response?.status === 409) emit('saved') }
  } finally { saving.value = false }
}
onBeforeUnmount(clearHistory)
</script>

<style scoped>
.development-group-progress{display:flex;flex-direction:column;align-items:flex-start;gap:3px;line-height:1.5}
.development-group-progress small{font-size:12px;color:var(--el-text-color-secondary);white-space:normal;overflow-wrap:anywhere}.group-arrow{margin-left:6px}
.group-history-body{max-height:min(560px,calc(100vh - 160px));overflow-y:auto;overflow-wrap:anywhere}.group-history-record{margin-bottom:12px}
</style>
<style>
.development-group-history{max-width:calc(100vw - 32px)!important;box-sizing:border-box}.development-group-history .el-descriptions__content{overflow-wrap:anywhere;white-space:pre-wrap}
@media(max-width:800px){.development-group-history{position:fixed!important;left:16px!important;right:16px!important;top:72px!important;transform:none!important;width:calc(100vw - 32px)!important}.development-group-history>.el-popper__arrow{display:none}}
</style>
