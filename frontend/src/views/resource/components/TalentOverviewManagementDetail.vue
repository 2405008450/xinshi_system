<template>
  <el-popover v-model:visible="visible" trigger="click" placement="left" :width="760" :title="groupId ? '企微大群详情' : '语种管理详情'" popper-class="overview-management-popover" @show="load">
    <template #reference><el-button link type="primary">查看详情</el-button></template>
    <div class="detail-body" v-loading="loading">
      <el-alert v-if="errorText" :title="errorText" type="error" :closable="false" />
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="语种/方言">{{ language }}</el-descriptions-item>
          <el-descriptions-item v-if="groupId" label="群名">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item v-if="groupId" label="是否已建">{{ detail.isBuilt ? '已建' : '未建' }}</el-descriptions-item>
          <el-descriptions-item v-if="groupId" label="建群日期">{{ formatOverviewDate(detail.builtDate) }}</el-descriptions-item>
          <el-descriptions-item v-if="groupId" label="最新统计日期">{{ formatOverviewDate(detail.statisticsDate) }}</el-descriptions-item>
          <el-descriptions-item v-if="groupId" label="最新人数">{{ formatOverviewCount(detail.peopleCount) }}</el-descriptions-item>
          <el-descriptions-item v-if="groupId" label="归档状态">{{ detail.archived ? '已归档' : '未归档' }}</el-descriptions-item>
          <el-descriptions-item label="最近操作人">{{ detail.operatorName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作时间">{{ formatOverviewOperationTime(detail.operatedAt) }}</el-descriptions-item>
          <el-descriptions-item label="计划" :span="2"><span class="long-text">{{ detail.plan || '-' }}</span></el-descriptions-item>
          <el-descriptions-item label="备注" :span="2"><span class="long-text">{{ detail.remarks || '-' }}</span></el-descriptions-item>
        </el-descriptions>
        <el-tabs v-model="activeTab">
          <el-tab-pane v-if="groupId" label="人数历史" name="counts">
            <el-table :data="counts.items" border size="small" class="counts-history-table">
              <el-table-column label="统计日期" width="125"><template #default="{ row }">{{ formatOverviewDate(row.statisticsDate) }}</template></el-table-column>
              <el-table-column prop="peopleCount" label="人数" width="70" />
              <el-table-column prop="operatorName" label="登记人" width="95" />
              <el-table-column label="登记时间" min-width="150"><template #default="{ row }">{{ formatOverviewOperationTime(row.operatedAt) }}</template></el-table-column>
              <el-table-column label="状态/作废信息" min-width="180"><template #default="{ row }">
                <span v-if="row.voidedAt" class="long-text">已作废：{{ row.voidReason }}<br />{{ row.voidedByName }} · {{ formatOverviewOperationTime(row.voidedAt) }}</span>
                <el-tag v-else :type="row.id === detail.latestCountId ? 'success' : 'info'" size="small">{{ row.id === detail.latestCountId ? '当前人数' : '有效记录' }}</el-tag>
              </template></el-table-column>
              <el-table-column v-if="writable && !detail.archived" label="操作" width="70" fixed="right"><template #default="{ row }">
                <el-button v-if="!row.voidedAt" link type="danger" @click="requestVoid(row)">作废</el-button>
              </template></el-table-column>
            </el-table>
            <el-pagination v-model:current-page="countPage" small layout="prev, pager, next, total" :total="counts.total" :page-size="10" @current-change="loadCounts" />
          </el-tab-pane>
          <el-tab-pane label="操作历史" name="audit">
            <el-table :data="history.items" border size="small">
              <el-table-column label="操作" width="120"><template #default="{ row }">{{ overviewOperationLabels[row.operation] || row.operation }}</template></el-table-column>
              <el-table-column label="修改前" min-width="180"><template #default="{ row }"><span class="long-text">{{ formatOverviewChange(row.before) }}</span></template></el-table-column>
              <el-table-column label="修改后" min-width="180"><template #default="{ row }"><span class="long-text">{{ formatOverviewChange(row.after) }}</span></template></el-table-column>
              <el-table-column prop="operatorName" label="操作人" width="95" />
              <el-table-column label="操作时间" min-width="155"><template #default="{ row }">{{ formatOverviewOperationTime(row.operatedAt) }}</template></el-table-column>
            </el-table>
            <el-pagination v-model:current-page="historyPage" small layout="prev, pager, next, total" :total="history.total" :page-size="10" @current-change="loadHistory" />
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>
  </el-popover>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getOverviewGroup, getOverviewGroupCounts, getOverviewGroupHistory, getOverviewLanguageHistory, getOverviewLanguageManagement } from '@/api/talents'
import { formatOverviewDate, formatOverviewCount, formatOverviewOperationTime, formatOverviewChange, overviewOperationLabels } from '@/utils/talentOverviewWecom'
const props = defineProps({ groupId: { type: String, default: '' }, overviewKey: { type: String, required: true }, language: { type: String, required: true }, writable: Boolean, reloadToken: { type: Number, default: 0 } })
const emit = defineEmits(['void'])
const visible = ref(false)
const loading = ref(false)
const detail = ref(null)
const errorText = ref('')
const activeTab = ref(props.groupId ? 'counts' : 'audit')
const counts = ref({ items: [], total: 0 })
const history = ref({ items: [], total: 0 })
const countPage = ref(1)
const historyPage = ref(1)
let countSequence = 0
let historySequence = 0
let loadSequence = 0
async function loadCounts() {
  const seq = ++countSequence
  try {
    const result = await getOverviewGroupCounts(props.groupId, countPage.value)
    if (seq === countSequence) counts.value = result
  } catch { if (seq === countSequence) errorText.value = '人数历史加载失败，请重新打开重试' }
}
async function loadHistory() {
  const seq = ++historySequence
  try {
    const result = await (props.groupId ? getOverviewGroupHistory(props.groupId, historyPage.value) : getOverviewLanguageHistory(props.overviewKey, historyPage.value))
    if (seq === historySequence) history.value = result
  } catch { if (seq === historySequence) errorText.value = '操作历史加载失败，请重新打开重试' }
}
async function load() {
  const seq = ++loadSequence
  ++countSequence
  ++historySequence
  loading.value = true
  errorText.value = ''
  detail.value = null
  countPage.value = historyPage.value = 1
  counts.value = history.value = { items: [], total: 0 }
  try {
    const result = await (props.groupId ? getOverviewGroup(props.groupId) : getOverviewLanguageManagement(props.overviewKey))
    if (seq !== loadSequence) return
    detail.value = result
    await Promise.all([props.groupId ? loadCounts() : Promise.resolve(), loadHistory()])
  } catch { if (seq === loadSequence) errorText.value = '详情加载失败，请重新打开重试' }
  finally { if (seq === loadSequence) loading.value = false }
}
function requestVoid(record) {
  visible.value = false
  emit('void', { group: detail.value, record })
}
watch(() => props.reloadToken, () => { if (visible.value) load(); else detail.value = null })
</script>

<style scoped>
.detail-body { max-height: 560px; overflow-y: auto; }
.long-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.el-pagination { margin-top: 12px; justify-content: flex-end; }
</style>
<style>
.overview-management-popover { max-width: calc(100vw - 32px); }
.overview-management-popover .el-descriptions__content { overflow-wrap: anywhere; }
</style>
