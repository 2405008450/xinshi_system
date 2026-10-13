<template>
  <section v-loading="loading" class="talent-original-data">
    <h4>合并前原始资料（冻结快照）</h4>
    <el-alert title="此处读取本次操作留存的原始资料，原主档也包含在内；后续编辑、再次合并及撤销不会改写这些原值。" type="info" :closable="false" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="overview">
      <p>留存时间：{{ formatBusinessDateTime(overview.frozen_at) }} · {{ overview.integrity_recorded ? '快照校验通过' : '旧审计快照（当时未保存校验值）' }}</p>
      <div class="original-toolbar"><el-select :model-value="personId" placeholder="选择合并前档案" :disabled="loading" style="width:min(460px, 100%)" @change="loadPerson"><el-option v-for="person in overview.people" :key="person.id" :value="person.id" :label="`${person.name} · ${person.code || person.id} · ${person.role}`" /></el-select><el-button :loading="exporting" @click="exportData">导出原始资料（JSON）</el-button></div>
      <div v-loading="personLoading">
        <el-descriptions v-if="personData" :column="2" border size="small" class="original-fields">
          <el-descriptions-item v-for="field in personData.fields" :key="field.key" :label="field.label" :span="Array.isArray(field.value) || (typeof field.value === 'string' && field.value.length > 100) ? 2 : 1"><div class="original-value">{{ fieldText(field) }}</div></el-descriptions-item>
        </el-descriptions>
        <h4 v-if="personAttachments.length">原附件</h4>
        <div v-for="attachment in personAttachments" :key="attachment.attachment_id" class="original-attachment">
          <el-button v-if="attachment.state === 'archived'" link type="primary" :loading="downloadingId === attachment.attachment_id" @click="downloadAttachment(attachment)">{{ attachment.original_name }} · 下载留存副本</el-button>
          <span v-else>{{ attachment.original_name }} · {{ attachment.message }}</span>
          <small v-if="attachment.message && attachment.state === 'archived'">{{ attachment.message }}</small>
        </div>
        <el-alert v-for="reference in externalReferences" :key="reference.field" :title="reference.message" type="warning" :closable="false" />
      </div>
      <p>合并前业务关联：{{ referencesText }}。原业务外键保持原档案 ID；导出包含当时的关联记录快照、全部字段、明细、附件记录及逐字段决策。附件文件通过留存副本分别下载。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getDuplicateOriginalData, exportDuplicateOriginalData, getDuplicateOriginalAttachment } from '@/api/talentDuplicateReview'
import { reviewDisplay } from '@/utils/talentDuplicateReview'
import { formatBusinessDateTime } from '@/utils/dateTime'
const props = defineProps({ operationId: { type: String, required: true } })
const overview = ref(null), personId = ref(''), personData = ref(null), error = ref(''), loading = ref(false), personLoading = ref(false), exporting = ref(false), downloadingId = ref('')
const personAttachments = computed(() => (overview.value?.attachments || []).filter(item => item.person_id === personId.value))
const externalReferences = computed(() => (overview.value?.external_references || []).filter(item => item.person_id === personId.value))
const referencesText = computed(() => Object.entries(overview.value?.reference_counts || {}).map(([table, count]) => `${table} ${count} 条`).join('、') || '无')
const fieldText = field => field.key.endsWith('_at') ? formatBusinessDateTime(field.value) : reviewDisplay(field.value)
const message = exception => { const value = exception.response?.data?.detail; return typeof value === 'string' ? value : value?.message || '原始资料读取失败' }
let controller, personController, sequence = 0, personSequence = 0
async function load() {
  controller?.abort(); personController?.abort(); controller = new AbortController(); const current = ++sequence; ++personSequence
  overview.value = null; personData.value = null; personId.value = ''; error.value = ''; loading.value = true
  try {
    const result = await getDuplicateOriginalData(props.operationId, {}, controller.signal)
    if (current !== sequence) return
    overview.value = result
    const target = result.people.find(person => person.role === '原主档') || result.people[0]
    if (target) await loadPerson(target.id)
  } catch (exception) { if (current === sequence && exception.code !== 'ERR_CANCELED') error.value = message(exception) }
  finally { if (current === sequence) loading.value = false }
}
async function loadPerson(id) {
  personController?.abort(); personController = new AbortController(); const current = ++personSequence
  personId.value = id; personData.value = null; personLoading.value = true; error.value = ''
  try { const result = await getDuplicateOriginalData(props.operationId, { person_id: id }, personController.signal); if (current === personSequence) personData.value = result }
  catch (exception) { if (current === personSequence && exception.code !== 'ERR_CANCELED') error.value = message(exception) }
  finally { if (current === personSequence) personLoading.value = false }
}
function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 10000)
}
async function exportData() {
  const operationId = props.operationId; exporting.value = true
  try { saveBlob(await exportDuplicateOriginalData(operationId), `人才合并原始资料-${operationId}.json`) }
  catch { ElMessage.error('原始资料导出失败，请重新加载后重试') }
  finally { exporting.value = false }
}
async function downloadAttachment(attachment) {
  downloadingId.value = attachment.attachment_id
  try { saveBlob(await getDuplicateOriginalAttachment(props.operationId, attachment.attachment_id), attachment.original_name) }
  catch { ElMessage.error('留存附件读取或校验失败，未下载文件') }
  finally { downloadingId.value = '' }
}
watch(() => props.operationId, load, { immediate: true })
onBeforeUnmount(() => { controller?.abort(); personController?.abort(); ++sequence; ++personSequence })
</script>

<style scoped>
.talent-original-data { border-top:1px solid var(--color-border); margin-top:20px; padding-top:8px }.talent-original-data p { overflow-wrap:anywhere; line-height:1.7 }.original-toolbar { display:flex; flex-wrap:wrap; gap:10px; margin:14px 0 }.original-value { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7 }.original-attachment { margin:10px 0 }.original-attachment small { display:block; color:var(--color-text-muted) }
@media(max-width:700px) { .original-fields :deep(.el-descriptions__cell) { overflow-wrap:anywhere; word-break:break-word } }
</style>
