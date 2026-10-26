<template>
  <DraggableFormDialog v-model="visible" title="开拓日志导入预览" width="min(1100px, calc(100vw - 32px))" top="5vh" class="development-import-preview">
    <el-alert title="本窗口只读取并比对 Excel，不会向数据库追加或修改记录。" type="info" :closable="false" />
    <div class="development-import-controls">
      <input type="file" accept=".xlsx" aria-label="选择资源开拓统筹表" @change="selectFile" />
      <el-button type="primary" :loading="loading" :disabled="!file" @click="preview">生成预览</el-button>
      <span v-if="file" class="muted">{{ file.name }}</span>
    </div>
    <template v-if="result">
      <p>工作表：{{ result.sheet }} · 有效行：{{ result.total }} · 已存在：{{ result.summary['已存在'] || 0 }} · 已存在有变化：{{ result.summary['已存在有变化'] || 0 }} · 可追加候选：{{ result.summary['可追加候选'] || 0 }} · 待核对：{{ result.summary['待核对'] || 0 }} · 旧库中本文件未出现：{{ result.old_not_in_file }}</p>
      <el-alert :title="result.note" type="warning" :closable="false" />
      <div class="development-import-issues">
        <el-tag v-for="[label, count] in issueSummary" :key="label" type="warning" effect="plain">{{ label }} {{ count }}</el-tag>
      </div>
      <div class="development-import-controls">
        <el-select v-model="decision" aria-label="筛选比对结果" style="width:180px"><el-option label="全部结果" value="" /><el-option label="待核对" value="待核对" /><el-option label="可追加候选" value="可追加候选" /><el-option label="已存在有变化" value="已存在有变化" /><el-option label="已存在" value="已存在" /></el-select>
        <el-input v-model="keyword" clearable placeholder="筛选行号、姓名、开拓人、问题" style="max-width:300px" />
      </div>
      <el-table :data="pagedRows" border size="small" height="min(440px, calc(100vh - 420px))" table-layout="fixed">
        <el-table-column type="expand" width="48"><template #default="{ row }"><el-descriptions title="原表内容与比对" :column="2" border size="small"><el-descriptions-item v-for="[label, value] in Object.entries(row.values)" :key="label" :label="label">{{ value || '-' }}</el-descriptions-item><el-descriptions-item label="手机号草案">{{ row.contact_mapping?.phone || '-' }}</el-descriptions-item><el-descriptions-item label="微信号草案">{{ row.contact_mapping?.wechat || '-' }}</el-descriptions-item><el-descriptions-item label="小红书号草案">{{ row.contact_mapping?.xiaohongshu || '-' }}</el-descriptions-item><el-descriptions-item label="其它联系方式原文">{{ row.contact_mapping?.other || '-' }}</el-descriptions-item><el-descriptions-item label="系统记录 ID">{{ row.existing_ids.join('、') || '-' }}</el-descriptions-item><el-descriptions-item label="识别语种">{{ row.languages.join('、') || '-' }}</el-descriptions-item><el-descriptions-item v-for="action in row.actions" :key="action.field" :label="`${action.field}动作草案`">{{ action.date || '日期待核对' }} · {{ action.operator || '操作人待核对' }} · {{ action.status || '状态待核对' }}<span v-if="action.issues.length">（{{ action.issues.join('；') }}）</span></el-descriptions-item></el-descriptions></template></el-table-column>
        <el-table-column prop="row" label="原表行" width="80" />
        <el-table-column prop="decision" label="比对结果" width="130"><template #default="{ row }"><el-tag :type="row.decision === '已存在' ? 'info' : row.decision === '可追加候选' ? 'success' : 'warning'">{{ row.decision }}</el-tag></template></el-table-column>
        <el-table-column prop="work_date" label="开拓日期" width="110" />
        <el-table-column label="开拓人" width="110"><template #default="{ row }">{{ row.values['开拓人/HR'] }}</template></el-table-column>
        <el-table-column label="姓名" width="130"><template #default="{ row }">{{ row.values['姓名'] || '-' }}</template></el-table-column>
        <el-table-column label="来源 → 平台" min-width="170"><template #default="{ row }">{{ row.values['来源'] || '-' }} → {{ row.platform || '-' }}</template></el-table-column>
        <el-table-column label="对接账号" min-width="130"><template #default="{ row }">{{ row.account || '-' }}</template></el-table-column>
        <el-table-column label="联系方式映射" min-width="190"><template #default="{ row }"><span class="development-import-wrap">{{ [row.contact_mapping?.phone && `手机 ${row.contact_mapping.phone}`, row.contact_mapping?.wechat && `微信 ${row.contact_mapping.wechat}`, row.contact_mapping?.xiaohongshu && `小红书 ${row.contact_mapping.xiaohongshu}`].filter(Boolean).join('；') || (row.contact_mapping?.other ? '原文待核' : '-') }}</span></template></el-table-column>
        <el-table-column label="语种" min-width="120"><template #default="{ row }">{{ row.values['语种'] || '-' }}</template></el-table-column>
        <el-table-column label="状态/跟进" width="105"><template #default="{ row }">{{ row.status_cells }} / {{ row.values['后续跟进情况'] ? 1 : 0 }}</template></el-table-column>
        <el-table-column label="需核对" min-width="240"><template #default="{ row }"><span class="development-import-wrap">{{ row.issues.join('；') || '-' }}</span></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="filteredRows.length" layout="total, prev, pager, next" />
    </template>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { developmentApi } from '@/api/resourceDevelopment'

const visible = ref(false), file = ref(null), loading = ref(false), result = ref(null)
const decision = ref(''), keyword = ref(''), page = ref(1), pageSize = 20
const issueSummary = computed(() => Object.entries(result.value?.issues || {}).sort((a, b) => b[1] - a[1]))
const filteredRows = computed(() => (result.value?.rows || []).filter(row => {
  if (decision.value && row.decision !== decision.value) return false
  const term = keyword.value.trim().toLocaleLowerCase()
  return !term || [row.row, row.values['姓名'], row.values['开拓人/HR'], ...row.issues].join(' ').toLocaleLowerCase().includes(term)
}))
const pagedRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch([decision, keyword], () => { page.value = 1 })
function selectFile(event) { file.value = event.target.files?.[0] || null; result.value = null; page.value = 1 }
async function preview() {
  if (!file.value || loading.value) return
  loading.value = true
  try { result.value = await developmentApi.importPreview(file.value); page.value = 1 }
  catch (error) { ElMessage.error(error.message || '导入预览失败') }
  finally { loading.value = false }
}
function open() { visible.value = true }
defineExpose({ open })
</script>

<style>
.development-import-preview.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.development-import-preview .el-dialog__header,.development-import-preview .el-dialog__footer{flex:none}
.development-import-preview .el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.development-import-preview .el-dialog__footer{border-top:1px solid var(--el-border-color-light);background:var(--el-fill-color-blank)}
.development-import-controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0}
.development-import-issues{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.development-import-wrap{white-space:normal;overflow-wrap:anywhere}
.development-import-preview .el-pagination{justify-content:flex-end;margin-top:10px}
</style>
