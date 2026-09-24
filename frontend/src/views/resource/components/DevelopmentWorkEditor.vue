<template>
  <DraggableFormDialog v-model="visible" width="min(800px, calc(100vw - 32px))" top="5vh" class="development-dialog" destroy-on-close :close-on-click-modal="false">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="每日开拓工作" placeholder="搜索字段，如工作时间段" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef"><AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
      <div class="development-form-grid">
        <el-form-item label="日期" prop="work_date"><el-date-picker v-model="form.work_date" value-format="YYYY-MM-DD" :clearable="false" :disabled="loaded" @change="loadWork" /></el-form-item>
        <el-form-item label="开拓人员" prop="owner_id"><el-select v-model="form.owner_id" filterable :disabled="loaded || !options.can_delegate" @change="loadWork"><el-option v-for="u in options.users" :key="u.id" :label="u.name" :value="u.id" /></el-select></el-form-item>
      </div>
      <el-form-item label="工作时间段" prop="periods"><div class="work-periods"><div v-for="(p, i) in form.periods" :key="i" class="period-row" data-dialog-field-search-group><span data-dialog-field-search-group-title>时段 {{ i + 1 }}</span><el-time-select v-model="p.start" start="00:00" end="23:59" step="00:01" placeholder="开始时间" /><span>至</span><el-time-select v-model="p.end" start="00:00" end="23:59" step="00:01" placeholder="结束时间" /><el-button text type="danger" @click="form.periods.splice(i, 1)">移除</el-button></div><el-button @click="form.periods.push({start:'09:00',end:'10:00'})">新增时间段</el-button></div></el-form-item>
      <div class="development-form-grid">
        <el-form-item label="手动扣减（分钟）" prop="deduction"><el-input-number v-model="form.deduction" :min="0" :precision="0" /></el-form-item>
        <el-form-item label="净工作时长"><ReadonlyField :model-value="`${minutes} 分钟`" source="auto" /></el-form-item>
        <el-form-item label="是否完成"><el-select v-model="form.completed"><el-option label="未填写" :value="'unset'" /><el-option label="是" :value="true" /><el-option label="否" :value="false" /></el-select></el-form-item>
      </div>
      <el-form-item label="完成情况说明" prop="explanation"><el-input v-model="form.explanation" type="textarea" :rows="4" maxlength="5000" /></el-form-item>
      <el-form-item label="打卡截图"><div><input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden @change="queueFiles" /><el-button @click="fileInput.click()">选择截图</el-button><p class="muted">支持 PNG、JPEG、WebP，每张不超过 5MB；点击保存后上传。</p><div v-for="s in screenshots" :key="s.id"><el-button link @click="preview(s)">{{ s.name }}</el-button><el-button text type="danger" @click="removeImage(s)">删除截图</el-button></div><div v-for="(file, i) in files" :key="i">{{ file.name }} <el-button text @click="files.splice(i, 1)">取消上传</el-button></div></div></el-form-item>
    </AppForm></div>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="previewVisible" title="打卡截图" width="min(900px, calc(100vw - 32px))" append-to-body><img v-if="previewUrl" :src="previewUrl" alt="打卡截图" style="max-width:100%;max-height:65vh" /></DraggableFormDialog>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { developmentApi as api } from '@/api/resourceDevelopment'
const props = defineProps({ options: { type: Object, required: true } }), emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), loaded = ref(false), formRef = ref(null), bodyRef = ref(null), files = ref([]), screenshots = ref([])
const fileInput = ref(null)
const previewVisible = ref(false), previewUrl = ref('')
const form = reactive({ work_date: '', owner_id: '', periods: [], deduction: 0, completed: 'unset', explanation: '', revision: 0 })
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const toMinutes = value => { const [h, m] = (value || '0:0').split(':').map(Number); return h * 60 + m }
const minutes = computed(() => form.periods.reduce((sum, p) => sum + toMinutes(p.end) - toMinutes(p.start), 0) - form.deduction)
const rules = computed(() => ({ work_date: [{ required: true, message: '请选择日期' }], owner_id: [{ required: true, message: '请选择开拓人员' }],
  periods: [{ validator: (_, value, cb) => { const sorted = [...value].sort((a, b) => a.start.localeCompare(b.start)); cb(sorted.some((p, i) => !p.start || !p.end || p.start >= p.end || (i && p.start < sorted[i-1].end)) ? new Error('时间段不能为空、倒序或重叠') : undefined) }, trigger: 'change' }],
  deduction: [{ validator: (_, v, cb) => cb(minutes.value < 0 ? new Error('扣减不能超过总时长') : undefined), trigger: 'change' }],
  explanation: form.completed === false ? [{ required: true, whitespace: true, message: '未完成时请填写说明', trigger: 'blur' }] : [],
}))
async function loadWork() { const row = await api.work({ work_date: form.work_date, owner_id: form.owner_id }); for (const key of Object.keys(form)) form[key] = key === 'completed' ? row[key] ?? 'unset' : row[key]; screenshots.value = row.screenshots; loaded.value = Boolean(row.id) }
async function open(day, owner) { form.work_date = day || props.options.default_date; form.owner_id = owner || props.options.user_id; files.value = []; await loadWork(); clearFieldSearch(); visible.value = true }
function queueFiles(event) { for (const file of event.target.files) { if (file.size > 5 * 1024 * 1024) ElMessage.warning(`${file.name} 超过5MB`); else files.value.push(file) } event.target.value = '' }
async function preview(s) { try { const blob = await api.screenshot(s.id); if (previewUrl.value) URL.revokeObjectURL(previewUrl.value); previewUrl.value = URL.createObjectURL(blob); previewVisible.value = true } catch (e) { ElMessage.error(e.message) } }
async function removeImage(s) { try { await ElMessageBox.confirm('确定删除这张打卡截图？', '删除截图'); await api.removeScreenshot(s.id); screenshots.value = screenshots.value.filter(x => x.id !== s.id) } catch (e) { if (e?.message) ElMessage.error(e.message) } }
async function save() {
  if (!await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    const row = await api.saveWork({ ...form, completed: form.completed === 'unset' ? null : form.completed }); form.revision = row.revision; loaded.value = true
    while (files.value.length) { const s = await api.upload(row.id, files.value[0]); screenshots.value.push(s); files.value.shift() }
    visible.value = false; emit('saved'); ElMessage.success('每日工作已保存并更新草稿日报')
  } catch (e) { ElMessage.error(e.message); emit('saved') } finally { saving.value = false }
}
onBeforeUnmount(() => { if (previewUrl.value) URL.revokeObjectURL(previewUrl.value) })
defineExpose({ open })
</script>
