<template>
  <div class="arrangement-panel">
    <DevelopmentDemandPanel ref="demandRef" @saved="saved" @changed="load(false)" />
    <div class="development-filters search-bar">
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" @change="query" />
      <el-button type="primary" @click="query">查询</el-button><el-button @click="selectTomorrow">明天</el-button>
      <template v-if="options.can_delegate"><el-date-picker v-model="editDate" value-format="YYYY-MM-DD" :clearable="false" aria-label="新增或编辑安排日期" /><el-button @click="openDate">明天/第二天</el-button><el-button @click="carry">沿用最近一次安排</el-button><el-button @click="emit('add-platform')">增加平台</el-button></template>
    </div>
    <p class="muted">每个账号每天一位负责人，多个语种和岗位统一确认完成；已完成表示当天安排已执行。沿用后可调整，保存才生效。</p>
    <div v-loading="loading">
      <el-empty v-if="!loading && !days.length" description="所选日期暂无安排" />
      <el-collapse v-model="expandedDates" class="arrangement-days">
        <el-collapse-item v-for="day in displayDays" :key="day.work_date" :name="day.work_date">
          <template #title>
            <div class="arrangement-day-heading">
              <strong>{{ chineseDate(day.work_date) }}</strong>
              <el-tag size="small" :type="day.revision ? 'success' : 'info'" effect="plain">{{ day.revision ? '已保存' : '尚未保存' }}</el-tag>
              <el-button v-if="options.can_delegate" link type="primary" @click.stop="edit(day)">编辑当日</el-button>
            </div>
          </template>
          <p class="arrangement-day-remarks">每日备注：{{ day.remarks || '-' }}</p>
          <el-table :data="day.rows" border class="arrangement-table" row-key="id" :span-method="arrangementTableSpan">
            <el-table-column label="大类" prop="categoryLabel" width="90" class-name="arrangement-group-cell" />
            <el-table-column label="平台" width="100" class-name="arrangement-group-cell"><template #default="{row}"><span :class="{muted: row.empty}">{{ row.empty ? '暂无平台' : row.platformName }}</span></template></el-table-column>
            <el-table-column label="账号" width="110"><template #default="{row}">{{ row.accountName }}</template></el-table-column>
            <el-table-column label="负责人" width="80"><template #default="{row}">{{ row.cell?.owner_name || '-' }}</template></el-table-column>
            <el-table-column label="语种／岗位目标" min-width="160">
              <template #default="{row}">
                <div class="arrangement-linked-projects"><DevelopmentArrangementProject v-for="project in row.cell?.projects || []" :key="`${project.source_type}:${project.project_id}`" :project="project" :day="day" :cell="row.cell" show-name /></div>
                <div class="arrangement-targets"><el-tag v-for="target in (row.cell?.targets || []).filter(t => !t.project)" :key="arrangementTargetKey(target)" :type="target.active === false ? 'warning' : 'info'" size="small"><span :title="target.source_name || target.request_no || ''">{{ target.label }}</span><span v-if="target.active === false"> · {{ target.inactive_reason }}</span></el-tag></div>
                <div class="arrangement-targets arrangement-roles"><el-tag v-for="role in row.cell?.role_tags || []" :key="role" size="small" type="success">{{ role }}</el-tag></div>
                <span v-if="!row.cell?.targets?.length && !row.cell?.role_tags?.length" class="muted">-</span>
                <small v-if="row.cell" class="arrangement-edit-operation muted">最近修改：{{ row.cell.operations?.edited?.actor_name || '未记录' }}<template v-if="row.cell.operations?.edited?.operated_at"> · {{ chineseTime(row.cell.operations.edited.operated_at) }}</template></small>
              </template>
            </el-table-column>
            <el-table-column label="完成状态" width="150">
              <template #default="{row}">
                <el-checkbox v-if="row.cell" :model-value="row.cell.completed" :disabled="!canEdit(row.cell) || !row.cell.owner_id || completing" :aria-label="`${day.work_date} ${row.name} 完成`" @update:model-value="value => complete(day, row.id, value)">{{ row.cell.completed ? '已完成' : '未完成' }}</el-checkbox>
                <span v-else class="muted">未安排</span>
                <small v-if="row.cell?.operations?.status || row.cell?.completed_by_name" class="arrangement-status-operation muted">{{ row.cell.operations?.status?.action === 'reopen' ? '取消完成' : row.cell.operations?.status?.action === 'reset' ? '变更重置' : '确认完成' }}：{{ row.cell.operations?.status?.actor_name || row.cell.completed_by_name }}<br>{{ chineseTime(row.cell.operations?.status?.operated_at || row.cell.completed_at) }}</small>
              </template>
            </el-table-column>
            <el-table-column label="详情" width="80" fixed="right"><template #default="{row}"><DevelopmentArrangementDetail v-if="!row.empty" :day="day" :account="row" :options="options" /></template></el-table-column>
            <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button v-if="!row.empty && !row.placeholder && (options.can_delegate || canEdit(row.cell))" link type="primary" @click="edit(day, row.id)">编辑安排</el-button><span v-else-if="!row.empty" class="muted">-</span></template></el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </div>
    <el-pagination v-if="total > pageSize" v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="load" />
    <DevelopmentArrangementEditor ref="editorRef" :options="options" @saved="saved" />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { arrangementTargetKey, arrangementToday, arrangementTomorrow, arrangementChineseDate as chineseDate, arrangementChineseTime as chineseTime, groupArrangementAccounts, arrangementTableRows, arrangementTableSpan } from '@/utils/resourceArrangements'
import DevelopmentArrangementEditor from './DevelopmentArrangementEditor.vue'
import DevelopmentArrangementDetail from './DevelopmentArrangementDetail.vue'
import DevelopmentDemandPanel from './DevelopmentDemandPanel.vue'
import DevelopmentArrangementProject from './DevelopmentArrangementProject.vue'
const props = defineProps({ options: { type: Object, required: true } }), emit = defineEmits(['add-platform'])
const tomorrow = arrangementTomorrow(), range = ref([tomorrow,tomorrow]), editDate = ref(tomorrow)
const days = ref([]), total = ref(0), page = ref(1), pageSize = 14, loading = ref(false), completing = ref(false), editorRef = ref()
const expandedDates = ref([]), demandRef = ref()
let controller, sequence = 0
const displayDays = computed(() => days.value.map(day => ({ ...day, rows: arrangementTableRows(groupArrangementAccounts(props.options, day.cells, { includePlaceholders: true })) })))
const canEdit = cell => Boolean(props.options.can_write && cell?.can_edit)
async function load(resetExpanded = true) {
  controller?.abort(); controller = new AbortController(); const seq = ++sequence; loading.value = true
  try {
    const [start,end] = range.value || [arrangementToday(),arrangementToday()]
    const data = await api.arrangements({start,end,skip:(page.value-1)*pageSize,limit:pageSize},controller.signal)
    if (seq !== sequence) return
    total.value = data.total; const last = Math.max(1,Math.ceil(data.total/pageSize))
    if (page.value > last) { page.value = last; return load(resetExpanded) }
    let items = data.items
    if (!items.length && start === end) items = [await api.arrangement(start,controller.signal)]
    if (seq === sequence) {
      days.value = items
      expandedDates.value = resetExpanded ? items.slice(0,1).map(day => day.work_date) : expandedDates.value.filter(date => items.some(day => day.work_date === date))
    }
  } catch (e) { if (seq === sequence && e.code !== 'ERR_CANCELED') ElMessage.error(e.message) }
  finally { if (seq === sequence) loading.value = false }
}
function query() { page.value = 1; if (range.value?.[0] === range.value?.[1]) editDate.value = range.value[0]; load() }
function selectTomorrow() { const tomorrow = arrangementTomorrow(); range.value = [tomorrow,tomorrow]; query() }
async function edit(day, platform) { try { await editorRef.value.open(await api.arrangement(day.work_date), platform) } catch (e) { ElMessage.error(e.message) } }
async function openDate() { if (editDate.value) await edit({work_date:editDate.value}) }
async function carry() { try { if (editDate.value) await editorRef.value.open(await api.carryArrangement(editDate.value)) } catch (e) { ElMessage.error(e.message) } }
async function saved(day) { range.value = [day.work_date,day.work_date]; editDate.value = day.work_date; page.value = 1; await Promise.all([load(), demandRef.value?.reload()]) }
async function complete(day, platform, completed) {
  if (completing.value) return
  completing.value = true
  try { const data = await api.completeArrangement(day.work_date,platform,{revision:day.revision,completed}); days.value = days.value.map(d => d.work_date === data.work_date ? data : d); await demandRef.value?.reload() }
  catch (e) { ElMessage.error(e.message); await load(false) }
  finally { completing.value = false }
}
onMounted(load)
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<style>
.arrangement-panel .development-filters{margin:12px 0;padding:12px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-page-bg)}.arrangement-panel .development-filters>.el-date-editor{max-width:310px}.arrangement-panel .development-filters>.el-input{width:160px}.arrangement-table .cell{white-space:normal;overflow-wrap:anywhere}.arrangement-owner,.arrangement-targets,.arrangement-linked-projects{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:4px 0}.arrangement-owner{justify-content:space-between}.arrangement-targets .el-tag{max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere}.arrangement-cell-remarks{white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0}.arrangement-table small{display:block}.arrangement-panel>.muted{margin:12px 0}
.arrangement-day-heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:8px 0}.arrangement-day-heading>.el-button{margin-left:auto}.arrangement-days .el-collapse-item__header{height:auto;min-height:48px}.arrangement-day-heading{flex:1;padding-right:12px}.arrangement-day-remarks{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--el-text-color-secondary);margin:8px 0 12px}.arrangement-table .el-checkbox{height:auto;white-space:normal;align-items:flex-start}.arrangement-table .el-checkbox__label{white-space:normal;padding-left:5px}.arrangement-table .el-checkbox__input{margin-top:3px}.arrangement-table .el-tag__content{min-width:0;white-space:normal;overflow-wrap:anywhere}
.arrangement-table .cell{padding-left:8px;padding-right:8px}.arrangement-table td.arrangement-group-cell{vertical-align:top}.arrangement-table td.arrangement-group-cell>.cell{padding-top:8px}
.arrangement-edit-operation,.arrangement-status-operation{font-size:12px;line-height:1.5;margin-top:6px}
</style>
