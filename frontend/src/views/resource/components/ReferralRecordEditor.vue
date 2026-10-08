<template>
  <DraggableFormDialog v-model="visible" class="referral-editor" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="!saving" :close-on-press-escape="!saving" :before-close="beforeClose" @closed="closed">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="mode === 'payment' ? '付款登记／更正' : form.revision ? '编辑推荐拓展' : '新增推荐拓展'" placeholder="搜索字段，如金额、拉人凭证" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="记录已被修改，请先重新加载。尚未上传的图片会保留，业务字段以最新记录为准。" type="warning" :closable="false"><el-button @click="reloadRecord">重新加载</el-button></el-alert>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving || loading">
        <template v-if="mode === 'payment'">
          <p>{{ form.full_name }} · {{ dateText(form.work_date) }} · 金额 {{ displayReferralValue(form, 'amount') }} 元</p>
          <el-form-item label="付款状态" prop="payment_status"><el-select v-model="form.payment_status" @change="paymentChanged"><el-option label="未支付" value="unpaid" /><el-option label="已支付" value="paid" /></el-select></el-form-item>
          <el-form-item v-if="form.payment_status === 'paid'" label="付款日期" prop="payment_date"><el-date-picker v-model="form.payment_date" type="date" value-format="YYYY-MM-DD" placeholder="选择实际付款日期" /></el-form-item>
        </template>
        <template v-else>
          <el-alert title="参考奖励：拉人3元、发圈5元、发群5元。金额请按实际情况手工填写。" type="info" :closable="false" />
          <div class="referral-form-grid">
            <el-form-item label="推广日期" prop="work_date"><el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" @change="checkDuplicates" /></el-form-item>
            <el-form-item label="推荐人姓名" prop="full_name"><el-input v-model="form.full_name" maxlength="255" @blur="checkDuplicates" /></el-form-item>
            <el-form-item label="推荐人微信" prop="wechat"><el-input v-model="form.wechat" maxlength="100" @blur="checkDuplicates" /></el-form-item>
            <el-form-item label="金额（元）" prop="amount"><el-input v-model="form.amount" inputmode="decimal" placeholder="手工填写，如3.00" /></el-form-item>
          </div>
          <el-alert v-if="duplicates.length" type="warning" :closable="false" title="同一日期、姓名和微信已有记录，建议打开已有记录补充；确认属于另一条记录时仍可保存。"><el-button v-for="row in duplicates" :key="row.id" link type="primary" @click="openDuplicate(row)">编辑 {{ row.full_name }} · {{ dateText(row.work_date) }}</el-button></el-alert>
          <el-form-item v-for="field in descriptionFields" :key="field.key" :label="field.label" :prop="field.key"><el-input v-model="form[field.key]" type="textarea" :rows="2" maxlength="20000" /></el-form-item>
          <el-form-item v-for="category in imageCategories" :key="category.key" :label="category.label" :prop="`images_${category.key}`">
            <div class="referral-upload-area"><p class="referral-muted">{{ category.hint }}；支持 PNG、JPEG、WebP，每张不超过5MB。</p>
              <ReferralImages :images="images.filter(i => i.category === category.key)" :editable="true" :disabled="saving || loading || conflict" @remove="removeImage" />
              <label class="referral-file-button"><span>{{ category.key === 'qr' ? '选择／替换收款码' : '选择图片' }}</span><input type="file" accept="image/png,image/jpeg,image/webp" :multiple="category.key !== 'qr'" :disabled="saving || loading" @change="queueFiles($event, category.key)" /></label>
              <div v-for="item in files.filter(i => i.category === category.key)" :key="item.id" class="referral-upload-draft"><span>{{ item.file.name }} <span v-if="item.error" class="referral-upload-error">{{ item.error }}</span></span><el-button link type="danger" :disabled="saving" @click="files = files.filter(i => i.id !== item.id)">取消上传</el-button></div>
            </div>
          </el-form-item>
        </template>
      </AppForm>
    </div>
    <template #footer><span v-if="files.length" class="referral-footer-hint">待上传 {{ files.length }} 张</span><el-button :disabled="saving" @click="closeEditor">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading || conflict" @click="save">{{ files.some(i => i.error) ? '保存并重试图片' : '保存' }}</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { referralApi as api } from '@/api/referralDevelopment'
import { newDevelopmentId } from '@/utils/resourceDevelopment'
import { dateText, displayReferralValue, imageCategories, today } from '@/utils/referralDevelopment'
import ReferralImages from './ReferralImages.vue'
const emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), loading = ref(false), mode = ref('record'), conflict = ref(false)
const formRef = ref(), bodyRef = ref(), files = ref([]), images = ref([]), duplicates = ref([])
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const empty = () => ({ id: newDevelopmentId(), revision: 0, work_date: today(), full_name: '', wechat: '', amount: '', pull_description: '', moments_description: '', groups_description: '', remarks: '', payment_status: 'unpaid', payment_date: null })
const form = reactive(empty())
const descriptionFields = [{ key: 'pull_description', label: '拉人说明' }, { key: 'moments_description', label: '发圈说明' }, { key: 'groups_description', label: '发群说明' }, { key: 'remarks', label: '备注' }]
const required = message => [{ required: true, whitespace: true, message, trigger: 'blur' }]
const rules = computed(() => mode.value === 'payment' ? { payment_status: required('请选择付款状态'), payment_date: form.payment_status === 'paid' ? required('请选择付款日期') : [] } : {
  work_date: required('请选择推广日期'), full_name: required('请填写推荐人姓名'),
  amount: [{ required: true, validator: (_, value, cb) => cb(/^(?:\d{1,10})(?:\.\d{1,2})?$/.test(String(value)) ? undefined : new Error('请填写非负金额，最多10位整数和2位小数')), trigger: 'blur' }],
})
let duplicateController, duplicateSeq = 0, openSeq = 0
function applyRecord(record) { for (const key of Object.keys(form)) if (key in record) form[key] = record[key]; form.amount = String(record.amount); images.value = record.images || [] }
async function open(row, newMode = 'record') {
  if (saving.value) return
  const seq = ++openSeq; duplicateController?.abort(); ++duplicateSeq
  mode.value = newMode; files.value = []; duplicates.value = []; images.value = []; conflict.value = false
  Object.assign(form, empty()); clearFieldSearch(); visible.value = true
  if (row) {
    loading.value = true
    try {
      const record = await api.detail(row.id)
      if (seq === openSeq) {
        applyRecord(record)
        if (newMode === 'payment' && form.payment_status === 'unpaid') { form.payment_status = 'paid'; form.payment_date = today() }
      }
    }
    catch (e) { if (seq === openSeq) { ElMessage.error(e.message); visible.value = false } }
    finally { if (seq === openSeq) loading.value = false }
  }
  await nextTick(); formRef.value?.clearValidate()
}
async function reloadRecord() {
  loading.value = true
  try { applyRecord(await api.detail(form.id)); conflict.value = false; formRef.value?.clearValidate(); emit('saved', form.id) }
  catch (e) { ElMessage.error(e.message) } finally { loading.value = false }
}
function paymentChanged() { form.payment_date = form.payment_status === 'paid' ? form.payment_date || today() : null }
async function checkDuplicates() {
  duplicateController?.abort(); const seq = ++duplicateSeq; duplicates.value = []
  if (!form.work_date || !form.full_name.trim() || !form.wechat.trim() || mode.value !== 'record') return
  duplicateController = new AbortController()
  try { const data = await api.duplicates({ work_date: form.work_date, full_name: form.full_name, wechat: form.wechat, exclude_id: form.id }, duplicateController.signal); if (seq === duplicateSeq) duplicates.value = data.items }
  catch (e) { if (seq === duplicateSeq && !['ERR_CANCELED','CanceledError','AbortError'].includes(e.code || e.name)) ElMessage.error(e.message) }
}
async function openDuplicate(row) {
  try { await ElMessageBox.confirm('打开已有记录将替换当前表单草稿，是否继续？', '打开已有记录', { confirmButtonText: '打开已有记录', cancelButtonText: '继续填写' }); await open(row) } catch { /* 用户继续填写当前记录。 */ }
}
function queueFiles(event, category) {
  const valid = [...event.target.files].filter(file => {
    if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) { ElMessage.warning(`${file.name}：请上传5MB以内的PNG、JPEG或WebP图片`); return false }
    return true
  })
  if (category === 'qr' && valid.length) files.value = files.value.filter(i => i.category !== 'qr')
  files.value.push(...valid.map(file => ({ id: newDevelopmentId(), file, category, error: '' })))
  event.target.value = ''
}
function handleError(e) { if (e.response?.status === 409 || e.status === 409) conflict.value = true; ElMessage.error(e.message) }
async function removeImage(image) {
  if (saving.value || loading.value) return
  try { await ElMessageBox.confirm('确定删除这张图片？删除将立即保存并记录操作历史。', '删除图片', { type: 'warning' }) } catch { return }
  saving.value = true
  try {
    const record = await api.removeImage(form, image.id)
    // 图片删除立即保存，保留尚未提交的业务字段草稿。
    form.revision = record.revision; images.value = record.images || []; emit('saved', form.id)
  }
  catch (e) { handleError(e) } finally { saving.value = false }
}
async function save() {
  if (saving.value || !await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    if (mode.value === 'payment') {
      applyRecord(await api.payment(form.id, { revision: form.revision, payment_status: form.payment_status, payment_date: form.payment_date }))
    } else {
      const { payment_status, payment_date, ...payload } = form
      applyRecord(await api.save(payload))
      for (const item of [...files.value]) {
        try { applyRecord(await api.upload(form, item)); files.value = files.value.filter(i => i.id !== item.id) }
        catch (e) { item.error = e.message; if (e.response?.status === 409 || e.status === 409) { conflict.value = true; break } }
      }
    }
    emit('saved', form.id)
    if (files.value.length) ElMessage.warning(`记录已保存，${files.value.length}张图片尚未上传，请查看错误并重试。`)
    else { visible.value = false; ElMessage.success('推荐拓展已保存') }
  } catch (e) { await formRef.value?.applyServerErrors(e); handleError(e) }
  finally { saving.value = false }
}
function beforeClose(done) { if (!saving.value) done() }
function closeEditor() { if (!saving.value) visible.value = false }
function closed() { ++openSeq; duplicateController?.abort(); ++duplicateSeq; files.value = []; images.value = []; duplicates.value = []; clearFieldSearch() }
onBeforeUnmount(() => { duplicateController?.abort(); ++openSeq })
defineExpose({ open })
</script>

<style>
.referral-editor{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.referral-editor>.el-dialog__header,.referral-editor>.el-dialog__footer{flex-shrink:0}.referral-editor>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.referral-editor>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc;display:flex;justify-content:flex-end;align-items:center;gap:12px}.referral-footer-hint{margin-right:auto;font-size:12px;color:#64748b}.referral-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}.referral-editor .el-alert{margin-bottom:16px}.referral-editor .el-date-editor,.referral-editor .el-select{width:100%}.referral-upload-area{width:100%}.referral-muted{color:#64748b;font-size:12px}.referral-file-button{display:inline-block;margin-top:12px;padding:6px 12px;border:1px solid #cbd5e1;border-radius:5px;position:relative;color:#334155;font-size:13px;cursor:pointer}.referral-file-button input{position:absolute;inset:0;opacity:0;width:100%;cursor:pointer}.referral-upload-draft{display:flex;justify-content:space-between;gap:12px;margin-top:8px;overflow-wrap:anywhere}.referral-upload-error{color:#b91c1c;font-size:12px;margin-left:8px}@media(max-width:640px){.referral-form-grid{grid-template-columns:1fr}.referral-editor .dialog-field-search-header{flex-wrap:wrap}.referral-editor .dialog-field-search-header__search{min-width:0;flex-basis:100%;width:100%}}
</style>
