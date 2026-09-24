<template>
  <section class="friend-daily-panel">
    <header><div><h3>群聊好友统计</h3><p>统计微信群聊途径的新增人数 · 使用上方日期范围，独立于逐人开拓筛选</p></div><el-button type="primary" plain :loading="opening" @click="open(today())">{{ options.can_write ? '填写每日统计' : '查看每日统计' }}</el-button></header>
    <el-table v-loading="loading" :data="days" border size="small" max-height="280" empty-text="所选日期尚无群聊统计，点击右上方按钮选择日期填写">
      <el-table-column label="日期" width="138" fixed="left"><template #default="{ row }"><el-button link type="primary" @click="open(row.work_date)">{{ formatDate(row.work_date) }}</el-button></template></el-table-column>
      <el-table-column v-for="channel in channels" :key="channel.key" :label="channel.label" align="center">
        <el-table-column v-for="a in options.accounts.filter(a => a.channel === channel.key)" :key="a.key" :label="shortName(a.label)" min-width="78" align="right"><template #header><el-tooltip :content="a.label"><span>{{ shortName(a.label) }}</span></el-tooltip></template><template #default="{ row }">{{ countFor(row, a.key) }}</template></el-table-column>
        <el-table-column label="小计" width="85" align="right"><template #default="{ row }"><strong>{{ row.totals[channel.key] }}</strong></template></el-table-column>
      </el-table-column>
      <el-table-column label="合计" width="85" fixed="right" align="right"><template #default="{ row }"><strong>{{ row.totals.wechat + row.totals.enterprise }}</strong></template></el-table-column>
    </el-table>
    <el-pagination v-if="total > 7" v-model:current-page="page" :page-size="7" :total="total" layout="total, prev, pager, next" @current-change="loadDays" />
    <DevelopmentFriendDailyEditor ref="editorRef" :options="options" @saved="loadDays" @options-changed="loadOptions" />
  </section>
</template>
<script setup>
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { friendDailyApi as api } from '@/api/resourceFriendDaily'
import DevelopmentFriendDailyEditor from './DevelopmentFriendDailyEditor.vue'
const props = defineProps({ range: { type: Array, required: true } })
const options = reactive({ accounts: [], languages: [], overview_rows: [], can_write: false })
const channels = [{ key: 'wechat', label: '微信新增人数' }, { key: 'enterprise', label: '企微新增人数' }]
const days = ref([]), total = ref(0), page = ref(1), loading = ref(false), opening = ref(false), editorRef = ref()
let controller, sequence = 0, optionSequence = 0
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
const formatDate = date => date.replaceAll('-', '/')
const shortName = label => label.match(/^HR\d+/i)?.[0] || label.replace(/^(微信|企微)·/, '')
const countFor = (day, key) => { const rows = day.rows.filter(r => r.column_key === key && r.count != null); return rows.length ? rows.reduce((n, r) => n + r.count, 0) : '-' }
async function loadOptions() { const current = ++optionSequence; try { const data = await api.options(); if (current === optionSequence) Object.assign(options, data) } catch (e) { ElMessage.error(e.message) } }
async function loadDays() {
  controller?.abort(); controller = new AbortController(); const current = ++sequence; loading.value = true
  try { const data = await api.list({ start: props.range[0], end: props.range[1], skip: (page.value - 1) * 7, limit: 7 }, controller.signal); if (current !== sequence) return; total.value = data.total; const last = Math.max(1, Math.ceil(data.total / 7)); if (page.value > last) { page.value = last; return loadDays() }; days.value = data.items }
  catch (e) { if (current === sequence && !['ERR_CANCELED','CanceledError','AbortError'].includes(e.code || e.name)) ElMessage.error(e.message) }
  finally { if (current === sequence) loading.value = false }
}
async function open(day = today()) { if (opening.value) return; opening.value = true; try { await loadOptions(); await editorRef.value.open(day) } finally { opening.value = false } }
watch(() => [...props.range], () => { page.value = 1; loadDays() }, { immediate: true })
loadOptions()
onBeforeUnmount(() => { sequence++; optionSequence++; controller?.abort() })
defineExpose({ open })
</script>
<style scoped>
.friend-daily-panel{margin:18px 0 22px;padding:16px;border:1px solid #e2e8f0;border-radius:10px;background:#fff}.friend-daily-panel>header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}.friend-daily-panel h3{font-size:16px;margin:0 0 6px}.friend-daily-panel p{margin:0;color:#64748b;font-size:12px;line-height:1.6}
@media(max-width:650px){.friend-daily-panel{padding:10px}}
</style>
