<template>
  <el-card class="common-page-card duplicate-review-page">
    <template #header>
      <div class="review-header">
        <div><strong>同名核重</strong><span class="subtitle">同名候选需人工确认身份；支持部分成员处理</span></div>
        <div><el-button @click="returnToList">返回人才列表</el-button><el-button @click="openHistory">处理历史</el-button></div>
      </div>
    </template>
    <el-alert v-if="!ready" title="数据库尚未启用核重结构，当前可只读比对。启用需要单独授权数据库迁移。" type="warning" :closable="false" show-icon />
    <el-alert v-else-if="!canOperate" title="当前账号仅可查看脱敏比对；处理与撤销由超级管理员执行。" type="info" :closable="false" />
    <AppForm :inline="true" class="review-query" :model="filters">
      <el-form-item label="姓名／编号"><el-input v-model="filters.keyword" clearable placeholder="搜索姓名或人才编号" @input="onInput" @keyup.enter="searchNow" /></el-form-item>
      <el-form-item label="处理状态"><el-select v-model="filters.status" @change="searchNow" style="width:150px"><el-option label="待核对" value="pending" /><el-option label="已区分" value="different" /><el-option label="暂缓处理" value="deferred" /><el-option label="全部" value="all" /></el-select></el-form-item>
      <el-form-item v-if="canOperate" label="Agent 初筛"><el-select v-model="filters.agent_bucket" @change="searchNow" style="width:190px"><el-option v-for="(label,key) in agentBucketLabels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" @click="searchNow">查询</el-button><el-button @click="reset">重置</el-button></el-form-item>
    </AppForm>
    <div class="group-counts">待核对 {{ counts.pending || 0 }} 组 · 已区分 {{ counts.different || 0 }} 组 · 暂缓 {{ counts.deferred || 0 }} 组</div>
    <div v-if="canOperate && agentSummary?.created_at" class="agent-summary">当前 Agent 已初筛 · {{ formatBusinessDateTime(agentSummary.created_at) }} · 高置信度同一人 {{ agentSummary.counts.high_same || 0 }} 组 · 二次核对 {{ agentSummary.counts.uncertain || 0 }} 组（同组可包含不同结论）</div>
    <div v-if="pageError" class="load-error"><el-alert :title="pageError" type="error" :closable="false" /><el-button @click="searchNow">重新加载</el-button></div>
    <div class="review-layout">
      <aside v-loading="loading" class="group-pane">
        <el-empty v-if="!loading && !items.length" description="当前条件没有同名组" :image-size="72" />
        <button v-for="group in items" :key="group.key" class="group-item" :class="{ active: currentKey === group.key }" @click="selectGroup(group.key)">
          <div><strong>{{ group.name }}</strong><el-tag size="small">{{ group.count }} 条</el-tag></div>
          <div>{{ reviewStateLabels[group.status] }}</div><small>{{ group.summary }}</small>
          <el-tag v-if="group.agent_review?.buckets.includes('high_same')" size="small" type="success">Agent：有高置信度重复</el-tag>
          <el-tag v-else-if="group.agent_review?.state === 'stale'" size="small" type="warning">初筛已过期，需重新核对</el-tag>
        </button>
        <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" small @current-change="loadGroups" />
      </aside>
      <main v-loading="detailLoading" class="comparison-pane">
        <el-alert v-if="detailError" :title="detailError" type="error" :closable="false" />
        <el-empty v-if="!detail && !detailLoading" description="选择左侧姓名组开始比对" />
        <template v-if="detail">
          <h3>{{ currentKey }} · {{ detail.members.length }} 条档案</h3>
          <div class="member-selection">
            <el-checkbox-group v-model="selectedIds" @change="clearPreview">
              <el-checkbox v-for="member in detail.members" :key="member.id" :value="member.id">
                {{ member.full_name }}（{{ member.resource_code || member.id.slice(0, 8) }}）· {{ member.project_situation?.total || 0 }} 个项目
              </el-checkbox>
            </el-checkbox-group>
          </div>
          <div class="comparison-controls"><span>已选择 {{ selectedIds.length }} 条；请选择至少两条进行处理</span><el-switch v-model="differencesOnly" active-text="只看差异（含互补）" /></div>
          <div v-if="canOperate && detail.agent_review" class="agent-results">
            <el-alert v-if="detail.agent_review.state === 'stale'" title="资料或组成员已变化，旧初筛建议已失效。" type="warning" :closable="false" />
            <template v-for="(suggestion,index) in detail.agent_review.pairs" :key="index">
              <div class="agent-pair"><el-tag :type="suggestion.bucket === 'high_same' ? 'success' : 'warning'" size="small">{{ agentBucketLabels[suggestion.bucket] }}</el-tag> {{ suggestion.person_ids.map(memberLabel).join(' ↔ ') }}</div>
              <div class="agent-reason">{{ suggestion.reason }}<div v-for="caution in suggestion.cautions" :key="caution">需核对：{{ caution }}</div></div>
              <el-button v-if="suggestion.classification === 'same'" :disabled="suggestion.confidence === 'high' && !ready" link type="primary" @click="useAgentSuggestion(suggestion)">{{ suggestion.confidence === 'high' ? '按这两条预览合并' : '选中这两条继续核对' }}</el-button>
            </template>
          </div>
          <div class="evidence-list">
            <div v-for="(pair, index) in visiblePairs" :key="index" class="pair-evidence">
              <span>{{ pair.person_ids.map(memberLabel).join(' ↔ ') }}</span>
              <el-tag v-if="pair.decision" size="small">{{ actionLabels[pair.decision] }}</el-tag>
              <el-tag v-for="match in pair.contact_matches || []" :key="match" type="success" size="small">{{ contactLabels[match] || match }}匹配</el-tag>
              <el-tag v-for="conflict in pair.identity_conflicts || []" :key="conflict" type="danger" size="small">{{ conflict }}</el-tag>
              <span v-if="pair.complement_count">{{ pair.complement_count }} 项资料互补</span>
            </div>
          </div>
          <div class="matrix-container">
            <el-table :data="matrixRows" border max-height="520" size="small" class="comparison-matrix">
              <el-table-column label="字段" width="160" fixed><template #default="{ row }">{{ row.label }}<br><el-tag :type="row.state === 'conflict' ? 'danger' : row.state === 'complement' ? 'warning' : 'info'" size="small">{{ fieldStateLabels[row.state] }}</el-tag></template></el-table-column>
              <el-table-column v-for="member in selectedMembers" :key="member.id" :label="`${member.full_name} · ${member.resource_code || member.id.slice(0,8)}`" min-width="235"><template #default="{ row }"><div class="matrix-value">{{ reviewDisplay(row.values[detail.members.findIndex(item => item.id === member.id)]) }}</div></template></el-table-column>
            </el-table>
          </div>
          <div v-if="canOperate && ready" class="review-actions">
            <el-button :disabled="selectedIds.length < 2" @click="beginAction('different')">确认不同人</el-button>
            <el-button :disabled="selectedIds.length < 2" @click="beginAction('defer')">暂缓处理</el-button>
            <el-button :disabled="selectedIds.length < 2" @click="beginAction('keep')">保留一条</el-button>
            <el-button type="primary" :disabled="selectedIds.length < 2" @click="beginAction('merge')">合并资料</el-button>
          </div>
        </template>
      </main>
    </div>

    <DraggableFormDialog v-model="actionVisible" width="min(1120px, calc(100vw - 32px))" top="5vh" class="review-action-dialog" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @closed="clearPreview">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :inert="saving" copyable-title :title="`${actionLabels[action]} · ${currentKey}`" :fetch-suggestions="fetchFieldSuggestions" placeholder="定位冲突字段，如性别" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="actionBodyRef" v-loading="previewLoading" class="action-body" :inert="saving">
        <AppForm :model="actionForm" label-position="top">
          <el-form-item v-if="['merge','keep'].includes(action)" label="保留档案（保留原编号与 ID）">
            <el-select v-model="targetId" style="width:100%" @change="targetChanged"><el-option v-for="member in selectedMembers" :key="member.id" :value="member.id" :label="`${member.full_name} · ${member.resource_code || member.id} · ${member.project_situation?.total || 0} 个项目${member.id === detail.recommended_target_id ? '（推荐）' : ''}`" /></el-select>
          </el-form-item>
          <el-form-item label="处理说明"><el-input v-model="note" type="textarea" :rows="2" maxlength="2000" @input="invalidatePreview" /></el-form-item>
        </AppForm>
        <el-alert v-if="action === 'different'" title="仅确认选中记录之间为不同人员，所有档案保留。资料变化后会重新提示核对。" type="info" :closable="false" />
        <el-alert v-if="action === 'defer'" title="暂缓所选记录之间的判断；可随时重新打开，资料变化后重新进入待核。" type="info" :closable="false" />
        <el-alert v-if="action === 'keep'" title="仅保留主档当前资料，其余所选档案归档，未并入的资料仍保留在原档案。" type="warning" :closable="false" />
        <el-alert v-if="action === 'merge'" title="空值补充、多值合并；每个冲突必须明确选择。原档案及业务历史均保留。" type="info" :closable="false" />
        <el-alert v-if="actionError" :title="actionError" type="error" :closable="false" />
        <div v-if="previewResult?.conflicts.length" class="conflicts">
          <h4>需要确认的冲突（{{ unresolvedCount }} 项未选择）</h4>
          <div v-for="conflict in previewResult.conflicts" :key="conflict.key" class="conflict-item" :data-dialog-field-search-label="conflict.label">
            <strong>{{ conflict.label }}</strong>
            <el-radio-group :model-value="choiceIds[conflict.key]" @change="value => chooseConflict(conflict, value)">
              <el-radio v-for="(option, index) in conflict.options" :key="index" :value="index"><div>{{ memberLabel(option.person_id) }}<div class="choice-value">{{ reviewDisplay(option.value) }}</div></div></el-radio>
              <el-radio v-if="!conflict.key.includes(':')" value="custom">人工修正</el-radio>
            </el-radio-group>
            <el-input v-if="choiceIds[conflict.key] === 'custom'" v-model="customValues[conflict.key]" placeholder="填写修正值；数字、布尔值及列表请使用 JSON 格式" @input="value => customChanged(conflict.key, value)" />
          </div>
        </div>
        <template v-if="previewResult">
          <h4>处理预览</h4>
          <div>归档：{{ previewResult.archive_ids.map(memberLabel).join('、') || '无' }}</div>
          <p>{{ previewResult.history_policy }}</p>
          <el-table v-if="previewResult.fields.length" :data="previewResult.fields" border size="small">
            <el-table-column prop="label" label="字段" width="170" /><el-table-column label="最终取值" min-width="240"><template #default="{ row }"><div class="matrix-value">{{ reviewDisplay(row.value) }}</div></template></el-table-column>
            <el-table-column label="来源原值" min-width="280"><template #default="{ row }"><div v-for="option in row.options" :key="option.person_id" class="matrix-value">{{ memberLabel(option.person_id) }}：{{ reviewDisplay(option.value) }}</div></template></el-table-column>
          </el-table>
          <div v-for="source in previewResult.omitted_fields" :key="source.person_id" class="omitted-fields"><h4>未并入资料：{{ memberLabel(source.person_id) }}</h4><div v-for="(field,index) in source.fields" :key="index" class="matrix-value">{{ field.label }}：{{ reviewDisplay(field.value) }}</div></div>
          <el-checkbox v-model="acknowledged" :disabled="!!previewResult.conflicts.length || previewDirty">已核对身份、最终资料及归档对象</el-checkbox>
        </template>
      </div>
      <template #footer><el-button :disabled="saving" @click="actionVisible = false">取消</el-button><el-button :disabled="saving || unresolvedCount > 0" :loading="previewLoading" @click="refreshPreview">{{ previewDirty || previewResult?.conflicts.length ? '更新预览' : '重新预览' }}</el-button><el-button type="primary" :loading="saving" :disabled="!previewResult || previewDirty || previewResult.conflicts.length > 0 || !acknowledged || previewLoading" @click="submitAction">确认{{ actionLabels[action] }}</el-button></template>
    </DraggableFormDialog>

    <DraggableFormDialog v-model="historyVisible" title="同名核重处理历史" width="min(960px, calc(100vw - 32px))" top="5vh" class="review-action-dialog">
      <el-table v-loading="historyLoading" :data="historyItems" border size="small">
        <el-table-column prop="name_key" label="姓名组" min-width="130" /><el-table-column label="操作" width="125"><template #default="{ row }">{{ actionLabels[row.action] }}</template></el-table-column><el-table-column prop="actor_name" label="操作人" width="110" /><el-table-column label="时间" min-width="170"><template #default="{ row }">{{ formatBusinessDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="状态" width="80"><template #default="{ row }">{{ row.undone_at ? '已撤销' : '已处理' }}</template></el-table-column>
        <el-table-column v-if="canOperate" label="详情" width="130" fixed="right"><template #default="{ row }">
          <el-popover v-for="(id,index) in row.person_ids" :key="id" trigger="click" placement="left" :width="760" title="人才核重档案详情" @show="loadHistoryTalent(id)">
            <template #reference><el-button link type="primary">档案 {{ index + 1 }} 详情</el-button></template>
            <TalentDetailContent v-loading="historyTalentLoading[id]" :detail="historyTalents[id] || {}" />
          </el-popover>
        </template></el-table-column>
        <el-table-column v-if="canOperate" label="操作" width="110" fixed="right"><template #default="{ row }"><el-button v-if="!row.undone_at" link type="warning" :loading="undoingId === row.id" @click="undoOperation(row)">撤销处理</el-button></template></el-table-column>
      </el-table>
      <template #footer><el-pagination v-model:current-page="historyPage" :page-size="20" :total="historyTotal" layout="total, prev, pager, next" @current-change="loadHistory" /><el-button @click="historyVisible = false">关闭</el-button></template>
    </DraggableFormDialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isSuperAdmin } from '@/utils/permission'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import TalentDetailContent from '@/views/resource/components/TalentDetailContent.vue'
import { getTalent } from '@/api/talents'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { actionLabels, fieldStateLabels, reviewStateLabels, reviewDisplay, selectedFieldState, buildReviewPayload } from '@/utils/talentDuplicateReview'
import { getDuplicateGroups, getDuplicateGroup, previewDuplicateReview, commitDuplicateReview, getDuplicateHistory, undoDuplicateReview } from '@/api/talentDuplicateReview'

const route = useRoute(), router = useRouter()
const actionBodyRef = ref(null)
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(actionBodyRef)
const canOperate = computed(() => isSuperAdmin())
const agentBucketLabels = { all:'全部结果', high_same:'高置信度同一人', likely_same:'可能同一人，需复核', different:'疑似不同人，需复核', uncertain:'证据不足，二次核对', unreviewed:'未初筛／资料已变化' }
const filters = reactive({ keyword: '', status: 'pending', agent_bucket: 'all' }), counts = ref({}), agentSummary = ref(null)
const items = ref([]), total = ref(0), page = ref(1), loading = ref(false), ready = ref(true), pageError = ref('')
const detail = ref(null), currentKey = ref(''), detailLoading = ref(false), detailError = ref(''), selectedIds = ref([]), differencesOnly = ref(true)
const contactLabels = { phone: '电话', email: '邮箱', wechat: '个人微信', whatsapp: 'WhatsApp', skype: 'Skype', line: 'Line' }
const selectedMembers = computed(() => detail.value?.members.filter(member => selectedIds.value.includes(member.id)) || [])
const visiblePairs = computed(() => detail.value?.pairs.filter(pair => pair.person_ids.every(id => selectedIds.value.includes(id))) || [])
const matrixRows = computed(() => (detail.value?.fields || []).map(row => ({ ...row, state: selectedFieldState(row.values.filter((value, index) => selectedIds.value.includes(detail.value.members[index].id))) })).filter(row => row.state !== 'missing' && (!differencesOnly.value || row.state !== 'same')))
const memberLabel = id => { const member = detail.value?.members.find(item => item.id === id); return member ? `${member.full_name} · ${member.resource_code || id.slice(0, 8)}` : id }
let timer, listController, detailController, listSequence = 0, detailSequence = 0, previewSequence = 0
const errorText = error => { const value = error.response?.data?.detail; return typeof value === 'string' ? value : value?.message || error.message || '加载失败，请重试' }
const cancelled = error => error.code === 'ERR_CANCELED' || error.name === 'CanceledError' || error.name === 'AbortError'
async function loadGroups() {
  clearTimeout(timer); listController?.abort(); listController = new AbortController(); const sequence = ++listSequence
  loading.value = true; pageError.value = ''
  try {
    const result = await getDuplicateGroups({ ...filters, skip: (page.value - 1) * 20, limit: 20 }, listController.signal)
    if (sequence !== listSequence) return
    items.value = result.items; total.value = result.total; counts.value = result.counts; ready.value = result.ready
    agentSummary.value = result.agent_summary || null
    if (!items.value.length && page.value > 1 && total.value) { page.value = Math.max(1, Math.ceil(total.value / 20)); return loadGroups() }
  } catch (error) { if (!cancelled(error) && sequence === listSequence) pageError.value = errorText(error) }
  finally { if (sequence === listSequence) loading.value = false }
}
function searchNow() { clearTimeout(timer); page.value = 1; loadGroups() }
function onInput(value) { clearTimeout(timer); if (!value) searchNow(); else timer = setTimeout(searchNow, 400) }
function reset() { filters.keyword = ''; filters.status = 'pending'; filters.agent_bucket = 'all'; searchNow() }
async function selectGroup(key) {
  detailController?.abort(); detailController = new AbortController(); const sequence = ++detailSequence
  currentKey.value = key; detail.value = null; selectedIds.value = []; detailLoading.value = true; detailError.value = ''; clearPreview()
  try {
    const result = await getDuplicateGroup(key, detailController.signal)
    if (sequence !== detailSequence) return
    detail.value = result; ready.value = result.ready; selectedIds.value = result.members.slice(0, 4).map(member => member.id)
  } catch (error) { if (!cancelled(error) && sequence === detailSequence) detailError.value = errorText(error) }
  finally { if (sequence === detailSequence) detailLoading.value = false }
}
function returnToList() { const path = String(route.query.return || '/resource-management/talents'); router.push(path.startsWith('/resource-management/') && !path.includes('//') ? path : '/resource-management/talents') }

const actionVisible = ref(false), action = ref('merge'), targetId = ref(''), note = ref(''), actionForm = reactive({})
const decisions = ref({}), choiceIds = ref({}), customValues = ref({}), previewResult = ref(null), previewDirty = ref(false), acknowledged = ref(false), actionError = ref(''), previewLoading = ref(false), saving = ref(false)
let idempotencyKey = ''
const unresolvedCount = computed(() => (previewResult.value?.conflicts || []).filter(conflict => !decisions.value[conflict.key]).length)
function invalidatePreview() { previewDirty.value = true; acknowledged.value = false; ++previewSequence; previewLoading.value = false; idempotencyKey = '' }
function clearPreview() { previewResult.value = null; decisions.value = {}; choiceIds.value = {}; customValues.value = {}; acknowledged.value = false; previewDirty.value = false; ++previewSequence; previewLoading.value = false; idempotencyKey = '' }
function targetChanged() { clearPreview(); refreshPreview() }
async function beginAction(value) { action.value = value; clearPreview(); note.value = ''; targetId.value = selectedIds.value.includes(detail.value.recommended_target_id) ? detail.value.recommended_target_id : selectedMembers.value[0].id; actionVisible.value = true; await refreshPreview() }
async function useAgentSuggestion(suggestion) { selectedIds.value = [...suggestion.person_ids]; clearPreview(); if (suggestion.confidence === 'high') await beginAction('merge') }
function chooseConflict(conflict, index) {
  choiceIds.value[conflict.key] = index
  if (index === 'custom') { decisions.value[conflict.key] = { value: null }; customValues.value[conflict.key] = '' }
  else { const option = conflict.options[index]; decisions.value[conflict.key] = { person_id: option.person_id, ...(option.value_hash ? { value_hash: option.value_hash } : {}) } }
  invalidatePreview()
}
function customChanged(key, value) { let parsed = value; try { parsed = JSON.parse(value) } catch {} decisions.value[key] = { value: parsed }; invalidatePreview() }
function payload() { return buildReviewPayload(action.value, selectedIds.value, targetId.value, decisions.value, note.value) }
async function refreshPreview() {
  const sequence = ++previewSequence; previewLoading.value = true; actionError.value = ''; acknowledged.value = false
  try { const result = await previewDuplicateReview(payload()); if (sequence !== previewSequence || !actionVisible.value) return; previewResult.value = result; previewDirty.value = false; idempotencyKey = crypto.randomUUID() }
  catch (error) { if (sequence === previewSequence) { actionError.value = errorText(error); previewDirty.value = true; if (previewResult.value?.conflicts.length) await locateDialogFieldByLabel(previewResult.value.conflicts[0].label) } }
  finally { if (sequence === previewSequence) previewLoading.value = false }
}
async function submitAction() {
  if (!previewResult.value || previewDirty.value || !acknowledged.value || previewResult.value.conflicts.length || saving.value) return
  saving.value = true; actionError.value = ''
  try { await commitDuplicateReview({ ...payload(), preview_token: previewResult.value.preview_token, idempotency_key: idempotencyKey }); historyTalents.value = {}; ElMessage.success('核重处理已保存'); actionVisible.value = false; await loadGroups(); await selectGroup(currentKey.value) }
  catch (error) { actionError.value = errorText(error); if ([409, 422].includes(error.response?.status)) invalidatePreview() }
  finally { saving.value = false }
}
const historyVisible = ref(false), historyItems = ref([]), historyPage = ref(1), historyTotal = ref(0), historyLoading = ref(false), undoingId = ref('')
const historyTalents = ref({}), historyTalentLoading = reactive({})
async function loadHistoryTalent(id) { if (historyTalents.value[id] || historyTalentLoading[id]) return; historyTalentLoading[id] = true; try { historyTalents.value[id] = await getTalent(id) } catch (error) { ElMessage.error(errorText(error)) } finally { historyTalentLoading[id] = false } }
async function loadHistory() { historyLoading.value = true; try { const result = await getDuplicateHistory({ skip: (historyPage.value - 1) * 20, limit: 20 }); historyItems.value = result.items; historyTotal.value = result.total } catch (error) { ElMessage.error(errorText(error)) } finally { historyLoading.value = false } }
function openHistory() { historyPage.value = 1; historyVisible.value = true; loadHistory() }
async function undoOperation(row) {
  try { await ElMessageBox.confirm('仅当档案、明细与业务关联均未变化且无后续核重时才能撤销。确认恢复本次处理前状态？', '撤销核重', { type: 'warning' }) } catch { return }
  undoingId.value = row.id
  try { await undoDuplicateReview(row.id); historyTalents.value = {}; ElMessage.success('处理已撤销'); await loadHistory(); await loadGroups(); if (currentKey.value) await selectGroup(currentKey.value) } catch (error) { ElMessage.error(errorText(error)) } finally { undoingId.value = '' }
}
onMounted(async () => { await loadGroups(); if (route.query.name) await selectGroup(String(route.query.name)) })
onBeforeUnmount(() => { clearTimeout(timer); listController?.abort(); detailController?.abort(); ++previewSequence })
</script>

<style scoped>
.review-header,.comparison-controls { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap }
.subtitle { margin-left:16px; color:#64748b; font-size:13px }
.agent-summary { margin-bottom:14px; color:#475569; font-size:13px }.agent-results { max-height:260px; overflow:auto; border:1px solid #e2e8f0; border-radius:8px; padding:12px; margin-bottom:14px }.agent-pair { font-size:13px; margin-top:8px }.agent-reason { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; line-height:1.6; color:#64748b; margin:6px 0 }
.review-query { margin-top:16px }.group-counts { color:#64748b; margin-bottom:14px }.review-layout { display:grid; grid-template-columns:260px minmax(0,1fr); gap:20px }.group-pane { min-width:0 }.group-item { display:block; text-align:left; width:100%; border:1px solid #e2e8f0; background:#fff; border-radius:8px; padding:12px; margin-bottom:10px; cursor:pointer; color:#334155 }.group-item.active { border-color:#3b82f6; background:#eff6ff }.group-item>div:first-child { display:flex; justify-content:space-between; gap:8px }.group-item small { display:block; margin-top:6px; color:#64748b }.comparison-pane { min-width:0 }.member-selection { max-height:180px; overflow:auto; border-bottom:1px solid #e2e8f0; padding-bottom:10px }.member-selection :deep(.el-checkbox-group) { display:flex; flex-direction:column }.comparison-controls { margin:14px 0; font-size:13px; color:#64748b }.pair-evidence { display:flex; flex-wrap:wrap; gap:6px; align-items:center; font-size:12px; margin-bottom:8px }.evidence-list { max-height:160px; overflow:auto; margin-bottom:12px }.matrix-container { min-width:0 }.matrix-value,.choice-value { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6 }.review-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; padding:14px 0; position:sticky; bottom:0; background:#fff; border-top:1px solid #e2e8f0 }.review-actions :deep(.el-button) { margin-left:0 }.conflict-item { border:1px solid #fecaca; border-radius:8px; padding:12px; margin:12px 0 }.conflict-item :deep(.el-radio-group) { display:flex; flex-direction:column; align-items:flex-start; margin-top:10px; gap:10px }.conflict-item :deep(.el-radio) { height:auto; white-space:normal; align-items:flex-start; max-width:100%; margin-right:0 }.conflict-item :deep(.el-radio__label) { white-space:normal; min-width:0 }.conflict-item :deep(.el-radio__input) { margin-top:4px }.choice-value { color:#475569; padding:4px 0 }.action-body>div,.action-body>p { margin-bottom:12px }.load-error { display:flex; gap:10px; margin-bottom:12px }.omitted-fields { padding:12px; background:#fff7ed; border-radius:8px }
@media(max-width:800px) { .review-layout { grid-template-columns:1fr }.group-pane { max-height:260px; overflow:auto }.subtitle { display:block; margin:6px 0 }.review-header>div:last-child { display:flex; flex-wrap:wrap; gap:6px } }
</style>
<style>
.review-action-dialog { display:flex; flex-direction:column; max-height:90vh; overflow:hidden }.review-action-dialog .el-dialog__header,.review-action-dialog .el-dialog__footer { flex-shrink:0 }.review-action-dialog .el-dialog__body { flex:1; min-height:0; overflow-y:auto }.review-action-dialog .el-dialog__footer { border-top:1px solid #e2e8f0; background:#f8fafc; display:flex; justify-content:flex-end; align-items:center; gap:8px; flex-wrap:wrap }
</style>
