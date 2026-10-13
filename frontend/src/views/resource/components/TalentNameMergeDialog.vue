<template>
  <DraggableFormDialog :model-value="modelValue" title="按姓名批量合并 · 全库预览" width="min(1180px, calc(100vw - 32px))" top="5vh" class="name-merge-dialog" :close-on-click-modal="!running" :close-on-press-escape="!running" :show-close="!running" @update:model-value="value => emit('update:modelValue', value)" @open="load" @closed="cancelLoading">
    <div v-loading="loading" class="name-merge-body">
      <el-alert title="按客户姓名规则直接合并，不使用 Agent 置信度：中文至少三个汉字，英文至少两个以空白分隔的单词；两个字的中文姓名跳过。" type="info" :closable="false" show-icon />
      <p>保留项目关联最多的档案，数量相同时保留较早创建的档案。单值冲突保留主档，空值补充，多值明细合并去重；其他联系方式、附件及冲突原值保留来源与历史关联。</p>
      <p v-if="summary">符合规则 {{ summary.total }} 组，预计归档 {{ summary.archive_count }} 条；其中中文 {{ summary.counts.chinese }} 组、英文 {{ summary.counts.english }} 组。跳过短中文姓名 {{ summary.counts.short_chinese }} 组、其他姓名 {{ summary.counts.other }} 组。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <p v-if="running || completed">成功 {{ successCount }} 组 · 失败 {{ failureCount }} 组 · 剩余 {{ remainingCount }} 组。停止会在当前组完成后生效；已完成组保留处理日志。</p>
      <el-table :data="pageRows" border size="small" class="name-merge-groups">
        <el-table-column label="姓名组" min-width="160"><template #default="{ row }">{{ row.key }}<br><el-tag size="small">{{ row.kind === 'chinese' ? '中文 ≥3 字' : '英文 ≥2 词' }}</el-tag></template></el-table-column>
        <el-table-column prop="count" label="档案数" width="80" />
        <el-table-column label="保留档案" min-width="160"><template #default="{ row }">{{ row.members[0].name }} · {{ row.members[0].code }}<br>{{ row.members[0].project_count }} 个项目</template></el-table-column>
        <el-table-column label="合并前全部档案" min-width="220"><template #default="{ row }">{{ row.members.map(member => member.code || member.id).join('、') }}</template></el-table-column>
        <el-table-column label="状态" min-width="180"><template #default="{ row }">{{ row.blocked_reason || outcomes[row.key]?.message || '待预览／执行' }}</template></el-table-column>
        <el-table-column label="详情" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" :disabled="running || !!row.blocked_reason" :loading="detailLoading && currentKey === row.key" @click="showPreview(row)">{{ outcomes[row.key]?.operation_id ? '查看合并记录' : '逐字段预览' }}</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="20" :total="rows.length" layout="total, prev, pager, next" />
      <h4 v-if="currentKey">{{ currentKey }} · {{ outcomes[currentKey]?.operation_id ? '合并记录' : '字段预览' }}</h4>
      <el-alert v-if="detailError" :title="detailError" type="error" :closable="false" />
      <TalentMergeAuditTable v-if="detailAudit" :audit="detailAudit" />
      <TalentOriginalData v-if="detailOperationId" :key="detailOperationId" :operation-id="detailOperationId" />
    </div>
    <template #footer>
      <el-checkbox v-model="acknowledged" :disabled="loading || running || completed">已确认按姓名规则处理全部符合条件的组，冲突原值留档</el-checkbox>
      <el-button v-if="running" @click="stopRequested = true" :disabled="stopRequested">{{ stopRequested ? '正在停止' : '停止后续处理' }}</el-button>
      <el-button v-else @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button :disabled="running" :loading="loading" @click="load">重新加载预览</el-button>
      <el-button type="primary" :disabled="loading || !rows.length || !acknowledged || running || completed" :loading="running" @click="execute">确认批量合并 {{ executableCount }} 组</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { getNameMergeGroups, previewNameMerge, commitNameMerge, getDuplicateOperation } from '@/api/talentDuplicateReview'
import TalentMergeAuditTable from './TalentMergeAuditTable.vue'
import TalentOriginalData from './TalentOriginalData.vue'
defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'processed'])
const rows = ref([]), summary = ref(null), page = ref(1), loading = ref(false), error = ref('')
const running = ref(false), stopRequested = ref(false), completed = ref(false), acknowledged = ref(false), outcomes = ref({})
const currentKey = ref(''), detailAudit = ref(null), detailLoading = ref(false), detailError = ref('')
const detailOperationId = ref('')
const pageRows = computed(() => rows.value.slice((page.value - 1) * 20, page.value * 20))
const executableCount = computed(() => rows.value.filter(row => !row.blocked_reason).length)
const successCount = computed(() => Object.values(outcomes.value).filter(row => row.success).length)
const failureCount = computed(() => Object.values(outcomes.value).filter(row => row.success === false).length)
const remainingCount = computed(() => executableCount.value - successCount.value - failureCount.value)
const message = exception => { const value = exception.response?.data?.detail; return typeof value === 'string' ? value : value?.message || exception.message || '加载失败' }
let controller, detailController, sequence = 0, detailSequence = 0
const previews = new Map(), requests = new Map()
function cancelLoading() { controller?.abort(); detailController?.abort(); ++sequence; ++detailSequence }
async function load() {
  if (running.value) return
  cancelLoading(); const current = sequence; controller = new AbortController()
  loading.value = true; error.value = ''; acknowledged.value = false; completed.value = false; outcomes.value = {}; rows.value = []; summary.value = null; page.value = 1; detailAudit.value = null; detailOperationId.value = ''; currentKey.value = ''; detailError.value = ''; detailLoading.value = false; previews.clear(); requests.clear()
  try {
    const collected = []; let skip = 0, total = 1
    while (skip < total) {
      const result = await getNameMergeGroups({ skip, limit: 100 }, controller.signal)
      if (current !== sequence) return
      summary.value = result; total = result.total
      collected.push(...result.items); skip += result.items.length
      if (!result.items.length) break
    }
    if (new Set(collected.map(row => row.key)).size !== collected.length || collected.length !== total) throw new Error('全库姓名组在扫描中变化，请重新加载预览')
    rows.value = collected
  } catch (exception) { if (current === sequence && exception.code !== 'ERR_CANCELED') error.value = message(exception) }
  finally { if (current === sequence) loading.value = false }
}
async function showPreview(row) {
  detailController?.abort(); detailController = new AbortController(); const current = ++detailSequence
  currentKey.value = row.key; detailAudit.value = null; detailOperationId.value = ''; detailError.value = ''; detailLoading.value = true
  try {
    const operationId = outcomes.value[row.key]?.operation_id
    const result = operationId ? await getDuplicateOperation(operationId) : await previewNameMerge({ group_key: row.key, group_version: row.group_version }, detailController.signal)
    if (current !== detailSequence) return
    detailAudit.value = result.audit
    detailOperationId.value = operationId || ''
    if (!operationId) previews.set(row.key, result)
  } catch (exception) { if (current === detailSequence && exception.code !== 'ERR_CANCELED') detailError.value = message(exception) }
  finally { if (current === detailSequence) detailLoading.value = false }
}
async function execute() {
  if (!acknowledged.value || running.value || loading.value || completed.value) return
  running.value = true; stopRequested.value = false; ++detailSequence; detailController?.abort(); detailLoading.value = false
  try {
    for (const row of rows.value.filter(item => !item.blocked_reason)) {
      if (stopRequested.value) break
      outcomes.value[row.key] = { message: '处理中' }
      try {
        let request = requests.get(row.key)
        if (!request) {
          const proposed = previews.get(row.key) || await previewNameMerge({ group_key: row.key, group_version: row.group_version })
          request = { group_key: row.key, group_version: row.group_version, preview_token: proposed.preview_token, idempotency_key: crypto.randomUUID() }
          requests.set(row.key, request)
        }
        const result = await commitNameMerge(request)
        outcomes.value[row.key] = { success: true, message: '已合并，日志已保存', operation_id: result.id }
      } catch (exception) { outcomes.value[row.key] = { success: false, message: message(exception) } }
    }
  } finally { running.value = false; completed.value = true; acknowledged.value = false; emit('processed') }
}
onBeforeUnmount(() => { stopRequested.value = true; cancelLoading() })
</script>

<style>
.name-merge-dialog { display:flex; flex-direction:column; max-height:90vh; overflow:hidden }
.name-merge-dialog .el-dialog__header,.name-merge-dialog .el-dialog__footer { flex-shrink:0 }
.name-merge-dialog .el-dialog__body { flex:1; min-height:0; overflow-y:auto }
.name-merge-dialog .el-dialog__footer { background:var(--color-surface-muted); border-top:1px solid var(--color-border); display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:10px }
.name-merge-dialog .el-dialog__footer .el-checkbox { height:auto; white-space:normal; margin-right:auto }
.name-merge-body p { line-height:1.7; overflow-wrap:anywhere }.name-merge-body .el-pagination { margin-top:12px }
</style>
