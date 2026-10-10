<template>
  <div class="arrangement-panel">
    <div class="development-filters">
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" @change="query" />
      <el-button type="primary" @click="query">查询</el-button><el-button @click="reset">今天</el-button>
      <template v-if="options.can_delegate"><el-date-picker v-model="editDate" value-format="YYYY-MM-DD" :clearable="false" aria-label="新增或编辑安排日期" /><el-button @click="openDate">新增／编辑安排</el-button><el-button @click="carry">沿用最近一次安排</el-button><el-button @click="emit('add-platform')">增加平台</el-button></template>
    </div>
    <p class="muted">每个账号每天一位负责人，多个语种和岗位统一确认完成；已完成表示当天安排已执行。沿用后可调整，保存才生效。</p>
    <el-table v-loading="loading" :data="days" border class="arrangement-table" row-key="work_date">
      <el-table-column label="日期" prop="work_date" width="125" fixed="left"><template #default="{row}">{{ chineseDate(row.work_date) }}<small v-if="!row.revision" class="muted">尚未保存</small></template></el-table-column>
      <el-table-column v-for="platform in platforms" :key="platform.id" :label="platform.name" :min-width="240">
        <template #default="{row}">
          <template v-if="cellFor(row, platform.id)">
            <div class="arrangement-owner">{{ cellFor(row, platform.id).owner_name || '暂未分配' }}
              <el-checkbox :model-value="cellFor(row, platform.id).completed" :disabled="!canEdit(cellFor(row, platform.id)) || !cellFor(row, platform.id).owner_id || completing" :aria-label="`${row.work_date} ${platform.name} 完成`" @update:model-value="value => complete(row, platform.id, value)">已完成</el-checkbox>
            </div>
            <div class="arrangement-targets"><el-tag v-for="target in cellFor(row, platform.id).targets" :key="arrangementTargetKey(target)" :type="target.active === false ? 'warning' : 'info'" size="small"><span :title="target.source_name || target.request_no || ''">{{ target.label }}</span><span v-if="target.active === false"> · {{ target.inactive_reason }}</span></el-tag></div>
            <div class="arrangement-targets arrangement-roles"><el-tag v-for="role in cellFor(row, platform.id).role_tags || []" :key="role" size="small" type="success">{{ role }}</el-tag></div>
          </template>
          <span v-else class="muted">未安排</span>
          <el-button v-if="options.can_delegate || canEdit(cellFor(row, platform.id))" link type="primary" @click="edit(row, platform.id)">编辑安排</el-button>
        </template>
      </el-table-column>
      <el-table-column label="详情" width="110" fixed="right"><template #default="{row}"><DevelopmentArrangementDetail :day="row" /></template></el-table-column>
      <el-table-column v-if="options.can_delegate" label="操作" width="110" fixed="right"><template #default="{row}"><el-button link type="primary" @click="edit(row)">编辑当日</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-if="total > pageSize" v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="load" />
    <DevelopmentArrangementEditor ref="editorRef" :options="options" @saved="saved" />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementTargetKey, arrangementToday, arrangementChineseDate as chineseDate } from '@/utils/resourceArrangements'
import DevelopmentArrangementEditor from './DevelopmentArrangementEditor.vue'
import DevelopmentArrangementDetail from './DevelopmentArrangementDetail.vue'
const props = defineProps({ options: { type: Object, required: true } }), emit = defineEmits(['add-platform'])
const today = arrangementToday(), range = ref([today,today]), editDate = ref(today)
const days = ref([]), total = ref(0), page = ref(1), pageSize = 14, loading = ref(false), completing = ref(false), editorRef = ref()
let controller, sequence = 0
const platforms = computed(() => {
  const map = new Map(props.options.options.filter(p => p.kind === 'platform').map(p => [p.id, {id:p.id,name:p.name}]))
  for (const day of days.value) for (const cell of day.cells) map.set(cell.platform_id, {id:cell.platform_id,name:cell.platform_name})
  return [...map.values()]
})
const cellFor = (day, platform) => day.cells.find(c => c.platform_id === platform)
const canEdit = cell => Boolean(props.options.can_write && cell?.can_edit)
async function load() {
  controller?.abort(); controller = new AbortController(); const seq = ++sequence; loading.value = true
  try {
    const [start,end] = range.value || [arrangementToday(),arrangementToday()]
    const data = await api.arrangements({start,end,skip:(page.value-1)*pageSize,limit:pageSize},controller.signal)
    if (seq !== sequence) return
    total.value = data.total; const last = Math.max(1,Math.ceil(data.total/pageSize))
    if (page.value > last) { page.value = last; return load() }
    let items = data.items
    if (!items.length && start === end) items = [await api.arrangement(start,controller.signal)]
    if (seq === sequence) days.value = items
  } catch (e) { if (seq === sequence && e.code !== 'ERR_CANCELED') ElMessage.error(e.message) }
  finally { if (seq === sequence) loading.value = false }
}
function query() { page.value = 1; if (range.value?.[0] === range.value?.[1]) editDate.value = range.value[0]; load() }
function reset() { range.value = [arrangementToday(),arrangementToday()]; query() }
async function edit(day, platform) { try { await editorRef.value.open(await api.arrangement(day.work_date), platform) } catch (e) { ElMessage.error(e.message) } }
async function openDate() { if (editDate.value) await edit({work_date:editDate.value}) }
async function carry() { try { if (editDate.value) await editorRef.value.open(await api.carryArrangement(editDate.value)) } catch (e) { ElMessage.error(e.message) } }
async function saved(day) { range.value = [day.work_date,day.work_date]; editDate.value = day.work_date; page.value = 1; await load() }
async function complete(day, platform, completed) {
  if (completing.value) return
  completing.value = true
  try { const data = await api.completeArrangement(day.work_date,platform,{revision:day.revision,completed}); days.value = days.value.map(d => d.work_date === data.work_date ? data : d) }
  catch (e) { ElMessage.error(e.message); await load() }
  finally { completing.value = false }
}
onMounted(load)
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<style>
.arrangement-panel .development-filters>.el-date-editor{max-width:310px}.arrangement-panel .development-filters>.el-input{width:160px}.arrangement-table .cell{white-space:normal}.arrangement-owner,.arrangement-targets,.arrangement-linked-projects{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:4px 0}.arrangement-owner{justify-content:space-between}.arrangement-targets .el-tag{height:auto;white-space:normal;overflow-wrap:anywhere}.arrangement-cell-remarks{white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0}.arrangement-table small{display:block}.arrangement-panel>.muted{margin:12px 0}
</style>
