<template>
  <DraggableFormDialog v-model="visible" title="三进度对比" width="min(1280px, calc(100vw - 32px))" top="5vh" append-to-body class="annotation-progress-comparison" @closed="cancel">
    <div class="progress-compare-identity"><b>{{ project?.orderNo }}</b><span class="progress-compare-project-name">{{ project?.projectName }}</span><el-tag size="small">{{ statusLabel(project?.projectStatus) }}</el-tag></div>
    <p class="progress-compare-hint">先看各条线的最新进度，再按同一日期对照记录。时间均为香港时间，最新日期在前；空白表示该条线当天暂无记录。</p>
    <div v-loading="loading">
      <div class="progress-compare-summary">
        <section v-for="track in comparison.tracks" :key="track.key" class="progress-compare-summary__card" :class="`is-${track.key}`">
          <header><b>{{ track.label }}</b><el-tag size="small" effect="plain">{{ track.rows.length }} 条</el-tag></header>
          <small>{{ track.hint }}</small>
          <el-alert v-if="errors[track.key]" :title="errors[track.key]" type="warning" :closable="false" />
          <template v-else-if="track.latest"><time>{{ formatTime(track.latest.effectiveOn) }}</time><p>{{ summaryText(track.latest, track.key) }}</p><small>{{ track.latest.changedByName || '系统' }}</small></template>
          <p v-else class="progress-compare-empty">{{ loading ? '正在加载…' : '暂无记录' }}</p>
        </section>
      </div>
      <div v-if="comparison.days.length" class="progress-compare-table" role="region" aria-label="三条进度按日期对照" tabindex="0">
        <div class="progress-compare-columns"><b>节点日期</b><b v-for="track in comparison.tracks" :key="track.key">{{ track.label }}</b></div>
        <div v-for="day in comparison.days" :key="day.day" class="progress-compare-day">
          <div class="progress-compare-date">{{ day.day }}</div>
          <section v-for="track in comparison.tracks" :key="track.key" :aria-label="`${day.day} ${track.label}`" class="progress-compare-cell">
            <p v-if="errors[track.key]" class="progress-compare-empty">加载失败，请重试</p>
            <p v-else-if="!day[track.key].length" class="progress-compare-empty">当天暂无记录</p>
            <article v-for="row in day[track.key]" :key="row.id" class="progress-compare-record" :class="{ 'is-latest': track.latest?.id === row.id }">
              <header><time>{{ row.businessTime.slice(11, 16) || '-' }}</time><el-tag v-if="track.latest?.id === row.id" size="small" effect="plain">最新</el-tag><span>{{ row.changedByName || '系统' }}</span></header>
              <el-tag v-if="track.key === 'project'" size="small" type="info">{{ statusLabel(row.toStatus) }}</el-tag>
              <ScreenshotText v-if="row.changeNote" :text="row.changeNote" />
              <p v-else class="progress-compare-empty">{{ track.key === 'project' ? '状态流转：' + statusLabel(row.toStatus) : '未填写说明' }}</p>
            </article>
          </section>
        </div>
      </div>
      <el-empty v-else-if="!loading" description="暂无可对比的进度记录" :image-size="64" />
    </div>
    <template #footer><el-button :loading="loading" @click="load">刷新三条进度</el-button><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { getStatusHistory, getCustomerProgress, getAnnotatorProgress } from '@/api/annotationOps'
import { annotationStatusLabel as statusLabel } from '@/utils/annotationStatus'
import { formatBusinessDateTimeMinute as formatTime } from '@/utils/dateTime'
import { compareProgressByDate, progressTracks } from '@/utils/annotationProgressComparison'
import { screenshotText } from '@/utils/screenshotReferences'

const visible = ref(false), loading = ref(false), project = ref(null), errors = ref({}), records = ref({})
const comparison = computed(() => compareProgressByDate(records.value))
let controller, version = 0
function cancel() { controller?.abort(); ++version; loading.value = false }
function summaryText(row, track) { return screenshotText(row.changeNote || '') || (track === 'project' ? '状态流转：' + statusLabel(row.toStatus) : '截图或附件记录') }
async function load() {
  if (!project.value?.id) return
  cancel()
  const current = version, id = project.value.id
  controller = new AbortController()
  const config = { signal: controller.signal }
  loading.value = true; errors.value = {}; records.value = {}
  const loaders = [getStatusHistory, getCustomerProgress, getAnnotatorProgress]
  await Promise.allSettled(progressTracks.map(async (track, index) => {
    try {
      const rows = await loaders[index](id, config)
      if (current === version) records.value = { ...records.value, [track.key]: rows }
    } catch (error) {
      if (current === version && error.code !== 'ERR_CANCELED') errors.value = { ...errors.value, [track.key]: error.detail || `${track.label}加载失败` }
    }
  }))
  if (current === version) loading.value = false
}
function open(value) { cancel(); project.value = value; visible.value = true; void load() }
onBeforeUnmount(cancel)
defineExpose({ open })
</script>

<style scoped>
.progress-compare-identity{display:flex;align-items:center;gap:12px;flex-wrap:wrap;color:#334155}.progress-compare-identity>b{color:#1e3a5f}.progress-compare-project-name{flex:1;min-width:180px;overflow-wrap:anywhere}
.progress-compare-hint{font-size:12px;color:#64748b;line-height:1.7;margin:12px 0 16px}
.progress-compare-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:20px}
.progress-compare-summary__card{min-width:0;padding:14px;border:1px solid #dbe3ee;border-top:3px solid #64748b;border-radius:8px;background:#f8fafc}.progress-compare-summary__card.is-customer{border-top-color:#3b82f6}.progress-compare-summary__card.is-annotator{border-top-color:#14b8a6}
.progress-compare-summary__card header,.progress-compare-record header{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.progress-compare-summary__card small{color:#64748b;font-size:12px}.progress-compare-summary__card time{display:block;margin-top:12px;font-size:12px;color:#475569}.progress-compare-summary__card p{line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden;margin:8px 0}
.progress-compare-table{overflow:auto;border:1px solid #e2e8f0;border-radius:8px;max-height:52vh}.progress-compare-columns,.progress-compare-day{display:grid;grid-template-columns:90px repeat(3,minmax(160px,1fr));min-width:570px}.progress-compare-columns{position:sticky;top:0;background:#edf2f7;z-index:1;font-size:13px}.progress-compare-columns>b{padding:14px}.progress-compare-date{padding:16px 10px;font-size:12px;font-weight:600;color:#475569;background:#f8fafc}.progress-compare-cell{padding:12px;min-width:0;border-left:1px solid #e2e8f0}.progress-compare-day{border-top:1px solid #e2e8f0}.progress-compare-record{padding:12px;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:10px;font-size:13px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}.progress-compare-record:last-child{margin-bottom:0}.progress-compare-record.is-latest{border-color:#b8cce7;background:#f8fbff}.progress-compare-record header{font-size:12px;color:#64748b;margin-bottom:8px}.progress-compare-empty{font-size:12px;color:#94a3b8}
@media(max-width:480px){.progress-compare-summary{grid-template-columns:1fr}.progress-compare-table{max-height:60vh}}
</style>
