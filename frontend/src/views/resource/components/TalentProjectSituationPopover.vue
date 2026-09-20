<template>
  <el-popover
    trigger="click"
    placement="left"
    :width="760"
    :title="`${personName} 参与项目`"
    popper-class="talent-project-situation-popper"
    @show="open"
    @hide="close"
  >
    <template #reference>
      <button v-if="summary?.primary" type="button" class="project-situation-reference">
        <span class="project-situation-reference__name">{{ summary.primary.projectName || '未命名项目' }}</span>
        <el-tag v-if="remainingCount" size="small" effect="plain">+{{ remainingCount }}</el-tag>
      </button>
      <span v-else>-</span>
    </template>

    <div class="project-situation-content">
      <div class="project-situation-filters">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索订单号、项目名称或参与角色"
          @input="handleKeywordInput"
          @keyup.enter="search"
        />
        <el-select v-model="filters.projectType" clearable placeholder="全部类型" @change="search">
          <el-option v-for="item in projectTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.projectStatus" clearable filterable placeholder="全部状态" @change="search">
          <el-option v-for="item in projectStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" border size="small" class="project-situation-table">
        <el-table-column label="类型" width="78"><template #default="{row}">{{ projectTypeLabel(row.projectType) }}</template></el-table-column>
        <el-table-column prop="orderNo" label="订单号" min-width="125" show-overflow-tooltip />
        <el-table-column label="项目名称" min-width="180">
          <template #default="{row}">
            <TalentProjectPerformancePopover :person-id="personId" :person-name="personName" :project="row" />
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="110" show-overflow-tooltip><template #default="{row}">{{ roleText(row) }}</template></el-table-column>
        <el-table-column label="状态" min-width="105" show-overflow-tooltip><template #default="{row}">{{ statusLabel(row.status) }}</template></el-table-column>
        <el-table-column label="参与时间" width="152"><template #default="{row}">{{ formatDateTime(row.participatedAt) }}</template></el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="暂无符合条件的参与项目" :image-size="64" />
      <el-pagination
        v-if="pagination.total > pagination.limit"
        v-model:current-page="pagination.page"
        :page-size="pagination.limit"
        :total="pagination.total"
        layout="total, prev, pager, next"
        small
        @current-change="load"
      />
    </div>
  </el-popover>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getTalentProjectPage } from '@/api/talents'
import TalentProjectPerformancePopover from './TalentProjectPerformancePopover.vue'

const props = defineProps({
  personId: { type: [String, Number], required: true },
  personName: { type: String, default: '人才' },
  summary: { type: Object, default: () => ({ total:0, primary:null }) },
})

const rows = ref([])
const loading = ref(false)
const filters = reactive({ keyword:'', projectType:'', projectStatus:'' })
const pagination = reactive({ page:1, limit:8, total:0 })
const remainingCount = computed(() => Math.max(0, Number(props.summary?.total || 0) - 1))
const projectTypeOptions = [
  {value:'translation',label:'笔译'}, {value:'interpretation',label:'口译'},
  {value:'annotation',label:'标注'}, {value:'recruitment',label:'招聘'},
]
const statusLabels = {
  initial_consultation:'初步咨询', consultation_no_result:'初步咨询后无结果', resource_sourcing:'资源开拓',
  resource_sourcing_cancelled:'取消资源开拓', trial_preparation:'试标准备', trial_in_progress:'试标中',
  trial_submitted:'试标已提交', trial_passed:'试标通过', trial_failed:'试标未通过',
  trial_partially_passed:'部分试标通过', project_in_progress:'项目进行中', sent_to_client:'已发客户',
  client_feedback:'客户反馈', pending:'待处理', in_progress:'进行中', completed:'已完成', cancelled:'已取消',
  partially_cancelled:'已部分取消', paused:'暂停', actively_abandoned:'主动放弃', ended:'已结束',
  screening:'筛选中', interview:'面试中', offered:'已发 Offer', hired:'已录用', rejected:'未通过',
}
const projectStatusOptions = Object.entries(statusLabels).map(([value,label]) => ({ value,label }))
const projectTypeLabel = value => projectTypeOptions.find(item => item.value === value)?.label || value || '-'
const statusLabel = value => statusLabels[value] || value || '-'
const roleText = row => row.roles?.length ? row.roles.map(value => ({annotator:'标注员',quality_inspector:'质检员'}[value] || value)).join('、') : row.role || '-'
const formatDateTime = value => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN', { hour12:false })
}

let timer = null
let controller = null
let sequence = 0
async function load() {
  controller?.abort()
  controller = new AbortController()
  const current = ++sequence
  loading.value = true
  try {
    const result = await getTalentProjectPage(props.personId, {
      keyword:filters.keyword.trim() || undefined,
      projectType:filters.projectType || undefined,
      projectStatus:filters.projectStatus || undefined,
      skip:(pagination.page - 1) * pagination.limit,
      limit:pagination.limit,
    }, { signal:controller.signal })
    if (current !== sequence) return
    rows.value = result?.items || []
    pagination.total = result?.total || 0
  } catch (error) {
    if (error?.code !== 'ERR_CANCELED' && current === sequence) {
      rows.value = []
      pagination.total = 0
      ElMessage.error(error?.detail || '加载人才参与项目失败')
    }
  } finally {
    if (current === sequence) loading.value = false
  }
}
const search = () => { clearTimeout(timer); pagination.page = 1; load() }
const handleKeywordInput = value => { clearTimeout(timer); if (!value?.trim()) return search(); timer = setTimeout(search, 400) }
const reset = () => { filters.keyword=''; filters.projectType=''; filters.projectStatus=''; search() }
const open = () => { pagination.page=1; load() }
const close = () => { clearTimeout(timer); controller?.abort(); sequence += 1 }
onBeforeUnmount(close)
</script>

<style>
.talent-project-situation-popper{max-width:calc(100vw - 32px)!important}
.project-situation-content{max-height:min(560px,calc(100vh - 120px));overflow-y:auto}
.project-situation-filters{position:sticky;top:0;z-index:2;display:grid;grid-template-columns:minmax(220px,1fr) 120px 140px auto;gap:8px;margin-bottom:10px;padding-bottom:10px;background:var(--el-bg-color)}
.project-situation-reference{display:flex;width:100%;min-width:0;align-items:center;gap:6px;padding:0;border:0;color:var(--el-color-primary);background:transparent;cursor:pointer}
.project-situation-reference__name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.project-situation-table{width:100%}
.project-situation-content .el-pagination{justify-content:flex-end;margin-top:10px}
@media(max-width:768px){.project-situation-filters{grid-template-columns:1fr 1fr}.project-situation-filters .el-input{grid-column:1/-1}}
</style>
