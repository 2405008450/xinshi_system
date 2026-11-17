<template>
  <el-popover trigger="click" placement="left" :width="760" title="人才编辑记录" popper-class="talent-edit-history-popper" @show="open" @hide="cancel">
    <template #reference><el-button link type="primary">编辑记录</el-button></template>
    <div class="history-body" v-loading="loading">
      <el-alert title="仅记录功能启用后的实际修改，无需填写原因。" type="info" :closable="false" />
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="load">重试</el-button></el-alert>
      <el-empty v-else-if="!loading && !items.length" description="暂无编辑记录" />
      <section v-for="item in items" :key="item.id" class="history-entry">
        <strong>{{ item.actorName }}（{{ item.actorAccount }}）</strong>
        <div>{{ formatBusinessDateTime(item.createdAt) }} · {{ sources[item.source] || item.source }}</div>
        <el-table :data="changeRows(item)" border size="small">
          <el-table-column prop="label" label="字段" width="140" />
          <el-table-column label="修改前" min-width="220"><template #default="{ row }"><div class="history-value">{{ display(row.before) }}</div></template></el-table-column>
          <el-table-column label="修改后" min-width="220"><template #default="{ row }"><div class="history-value">{{ display(row.after) }}</div></template></el-table-column>
        </el-table>
      </section>
    </div>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
  </el-popover>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { getTalentEditHistory } from '@/api/talents'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { talentAuditLabels } from '@/utils/talentAuditLabels'

const props = defineProps({ personId: { type: String, required: true } })
const items = ref([]), total = ref(0), page = ref(1), loading = ref(false), error = ref('')
const sources = { manual: '人工编辑', quick_name: '快捷修改姓名', quick_status: '快捷修改状态', path_edit: '路径窗口编辑', recruitment: '招聘端编辑', resume_import: '简历补充导入', import: '批量导入' }
let controller, sequence = 0
function cancel() { controller?.abort(); sequence++; loading.value = false }
function open() { page.value = 1; items.value = []; total.value = 0; load() }
async function load() {
  cancel(); controller = new AbortController(); const current = ++sequence
  loading.value = true; error.value = ''
  try {
    const data = await getTalentEditHistory(props.personId, { skip: (page.value - 1) * 20, limit: 20 }, { signal: controller.signal })
    if (current === sequence) { items.value = data.items; total.value = data.total }
  } catch (failure) {
    if (current === sequence && failure.code !== 'ERR_CANCELED') error.value = failure.detail || failure.message || '编辑记录加载失败'
  } finally { if (current === sequence) loading.value = false }
}
function label(key) {
  const normalized = key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
  return talentAuditLabels[normalized] || normalized.split('.').map(part => talentAuditLabels[part] || part).join(' / ')
}
function changeRows(item) { return Object.entries(item.changes).map(([key, change]) => ({ label: label(key), ...change })) }
function display(value) {
  if (value == null || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.length ? value.map(display).join('\n') : '-'
  if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${label(key)}：${display(item)}`).join('\n')
  return String(value)
}
watch(() => props.personId, () => { cancel(); items.value = []; total.value = 0; page.value = 1 })
onBeforeUnmount(cancel)
</script>

<style scoped>
.history-body{max-height:min(560px,calc(100vh - 180px));overflow-y:auto}
.history-entry{margin:14px 0}.history-entry>div{margin:4px 0;color:var(--el-text-color-secondary)}
.history-value{white-space:pre-wrap;overflow-wrap:anywhere}
</style>
<style>.talent-edit-history-popper{max-width:calc(100vw - 32px)!important}</style>
