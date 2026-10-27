<template>
  <section class="identity-workspace">
    <p class="identity-summary">{{ members.length }} 条档案 · {{ identity.counts?.recommended_subgroups || 0 }} 个建议合并子组 · {{ standalone.length }} 条单独保留 · {{ identity.counts?.unresolved_pairs || 0 }} 对关系未完成核对</p>
    <el-alert title="子组是核对建议，仍需逐组预览并确认。单独保留不表示已确认与其他人不同。" type="info" :closable="false" />
    <el-alert v-if="identity.ambiguous_pairs?.length" title="存在链式、重叠或矛盾候选，未强行划分子组，请在关系矩阵中逐对核对。" type="warning" :closable="false" />
    <div v-if="canOperate" class="draft-toolbar"><el-button :disabled="selectedIds.length < 2" @click="addDraft">将当前勾选存为子组</el-button><span>子组调整只用于本次预览，不修改人才资料。</span></div>
    <div class="subgroup-grid">
      <article v-for="(group,index) in drafts" :key="group.id" class="subgroup-card" :data-subgroup-id="group.id">
        <h4>{{ group.manual ? '自定义子组' : '建议合并子组' }} {{ index + 1 }} <el-tag size="small">{{ group.person_ids.length }} 条</el-tag></h4>
        <el-select v-if="canOperate" :model-value="group.person_ids" multiple :aria-label="`子组 ${index + 1} 成员`" @change="ids => editDraft(group, ids)">
          <el-option v-for="member in members" :key="member.id" :value="member.id" :label="memberLabel(member.id)" :disabled="drafts.some(other => other.id !== group.id && other.person_ids.includes(member.id))" />
        </el-select>
        <div v-else>{{ group.person_ids.map(memberLabel).join('、') }}</div>
        <label class="target-label">保留档案（保留原编号）</label>
        <el-select v-model="group.target_id" :aria-label="`子组 ${index + 1} 保留档案`">
          <el-option v-for="id in group.person_ids" :key="id" :value="id" :label="memberLabel(id)" />
        </el-select>
        <div v-for="(basis,i) in group.basis || []" :key="i" class="subgroup-basis">{{ basis.reason }}</div>
        <div v-if="group.manual" class="subgroup-basis">成员已人工调整，身份仍需自行核对；不沿用原子组的高置信度结论。</div>
        <div class="subgroup-actions"><el-button size="small" @click="emit('compare', group)">对照此子组</el-button><el-button v-if="canOperate" type="primary" size="small" :disabled="!ready || group.person_ids.length < 2" @click="emit('preview', group)">预览合并</el-button><el-button v-if="canOperate" link type="danger" @click="drafts = drafts.filter(item => item.id !== group.id)">移出子组</el-button></div>
      </article>
    </div>
    <div v-if="standalone.length" class="standalone-records"><strong>单独保留、身份待核：</strong><el-button v-for="id in standalone" :key="id" link @click="emit('compare', { person_ids: [id] })">{{ memberLabel(id) }}</el-button></div>
    <div v-if="canOperate" class="different-groups">
      <span>仅区分两个子组之间的关系：</span>
      <el-select v-model="leftGroup" aria-label="左侧子组" placeholder="选择左侧子组"><el-option v-for="option in groupOptions" :key="option.id" :value="option.id" :label="option.label" /></el-select>
      <el-select v-model="rightGroup" aria-label="右侧子组" placeholder="选择右侧子组"><el-option v-for="option in groupOptions" :key="option.id" :value="option.id" :label="option.label" :disabled="option.id === leftGroup" /></el-select>
      <el-button :disabled="!ready || !leftGroup || !rightGroup || leftGroup === rightGroup" @click="distinguish">预览确认不同人</el-button>
    </div>
    <h4>逐对关系矩阵 <small>点击单元格对照两条档案；Agent 建议不等于人工结论</small></h4>
    <el-table :data="members" border size="small" max-height="280" class="identity-pair-matrix">
      <el-table-column label="档案" width="160" fixed><template #default="{ row }">{{ row.resource_code || row.full_name }}</template></el-table-column>
      <el-table-column v-for="member in members" :key="member.id" :label="member.resource_code || member.full_name" min-width="160">
        <template #default="{ row }"><span v-if="row.id === member.id">—</span><el-button v-else link :type="relation(row.id,member.id).type" :title="relationTitle(row.id,member.id)" @click="emit('compare', { person_ids: [row.id,member.id] })">{{ relation(row.id,member.id).label }}</el-button></template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crossDecisionPairs, pairRelation, validateIdentityDraft } from '@/utils/talentDuplicateReview'

const props = defineProps({ groupKey: String, identity: { type: Object, default: () => ({}) }, members: { type: Array, default: () => [] },
  pairs: { type: Array, default: () => [] }, agent: { type: Object, default: () => ({}) }, selectedIds: { type: Array, default: () => [] }, canOperate: Boolean, ready: Boolean })
const emit = defineEmits(['compare', 'preview', 'distinguish'])
const drafts = ref([]), leftGroup = ref(''), rightGroup = ref('')
let loadedKey = '', versions = {}
const pairKey = ids => [...ids].sort().join('|')
const memberLabel = id => { const member = props.members.find(item => item.id === id); return member ? `${member.full_name} · ${member.resource_code || id.slice(0,8)}` : id }
watch(() => props.identity, value => {
  const currentVersions = value.member_versions || {}
  const kept = loadedKey === props.groupKey ? drafts.value.filter(group => group.person_ids.every(id => currentVersions[id] && currentVersions[id] === versions[id])) : []
  const assigned = new Set(kept.flatMap(group => group.person_ids))
  drafts.value = [...kept, ...(value.subgroups || []).filter(group => group.person_ids.every(id => !assigned.has(id))).map(group => ({ ...group,
    target_id: props.members.find(member => group.person_ids.includes(member.id))?.id }))]
  loadedKey = props.groupKey; versions = currentVersions; leftGroup.value = ''; rightGroup.value = ''
}, { immediate: true })
const standalone = computed(() => props.members.map(member => member.id).filter(id => !drafts.value.some(group => group.person_ids.includes(id))))
const groupOptions = computed(() => [...drafts.value.map((group,index) => ({ id: group.id, person_ids: group.person_ids, label: `子组 ${index + 1}（${group.person_ids.length} 条）` })),
  ...standalone.value.map(id => ({ id: `single:${id}`, person_ids: [id], label: memberLabel(id) }))])
const evidence = computed(() => new Map(props.pairs.map(pair => [pairKey(pair.person_ids), pair])))
const suggestions = computed(() => new Map((props.agent.pairs || []).map(pair => [pairKey(pair.person_ids), pair])))
function relation(a,b) { const key = pairKey([a,b]); return pairRelation(evidence.value.get(key), suggestions.value.get(key)) }
function relationTitle(a,b) { const key = pairKey([a,b]); const pair = evidence.value.get(key); return [...(pair?.identity_conflicts || []), suggestions.value.get(key)?.reason || '', ...(suggestions.value.get(key)?.cautions || [])].filter(Boolean).join('；') }
function addDraft() {
  const message = validateIdentityDraft(props.selectedIds, drafts.value)
  if (message) return ElMessage.warning(message)
  drafts.value.push({ id: crypto.randomUUID(), person_ids: [...props.selectedIds], target_id: props.members.find(member => props.selectedIds.includes(member.id))?.id, manual: true, basis: [] })
}
function editDraft(group, ids) {
  const message = validateIdentityDraft(ids, drafts.value, group.id)
  if (message) return ElMessage.warning(message)
  group.person_ids = [...ids]; group.manual = true; group.basis = []; group.report_id = null
  if (!ids.includes(group.target_id)) group.target_id = props.members.find(member => ids.includes(member.id))?.id
}
function distinguish() {
  const left = groupOptions.value.find(group => group.id === leftGroup.value), right = groupOptions.value.find(group => group.id === rightGroup.value)
  if (!left || !right) return
  try { emit('distinguish', { person_ids: [...left.person_ids,...right.person_ids], decision_pairs: crossDecisionPairs(left.person_ids,right.person_ids) }) }
  catch (error) { ElMessage.warning(error.message) }
}
</script>

<style scoped>
.identity-workspace { margin:12px 0; min-width:0 }.identity-summary { font-weight:600 }.identity-workspace :deep(.el-alert) { margin-bottom:10px }.draft-toolbar,.subgroup-actions,.different-groups { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:12px 0 }.draft-toolbar span,.subgroup-basis,small { color:var(--color-text-secondary); font-size:12px }.subgroup-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr)); gap:12px }.subgroup-card { min-width:0; padding:12px; border:1px solid var(--el-border-color); border-radius:8px; background:var(--color-surface) }.subgroup-card h4 { margin:0 0 10px }.subgroup-card .el-select { width:100% }.target-label { display:block; margin:10px 0 6px; font-size:12px }.subgroup-basis { margin-top:8px; white-space:pre-wrap; overflow-wrap:anywhere }.standalone-records { padding:12px 0 }.standalone-records .el-button { white-space:normal; height:auto; text-align:left; margin:4px }.different-groups .el-select { width:210px; max-width:100% }.identity-pair-matrix :deep(.el-button) { height:auto; white-space:normal; text-align:left }.identity-workspace h4 small { font-weight:400 }
</style>
