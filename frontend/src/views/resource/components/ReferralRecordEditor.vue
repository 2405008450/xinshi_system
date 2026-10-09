<template>
  <DraggableFormDialog v-model="visible" class="referral-editor" width="min(960px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="!saving" :close-on-press-escape="!saving" :before-close="beforeClose" @closed="closed">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" :title="mode === 'payment' ? '付款登记／更正' : form.revision ? '编辑推荐拓展' : '新增推荐拓展'" placeholder="搜索字段，如金额、拉人凭证" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading">
      <el-alert v-if="conflict" title="记录已被修改，请先重新加载。尚未上传的图片会保留，业务字段以最新记录为准。" type="warning" :closable="false"><el-button @click="reloadRecord">重新加载</el-button></el-alert>
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving || loading || conflict">
        <template v-if="mode === 'payment'">
          <p>{{ form.full_name }} · {{ dateText(form.work_date) }} · 金额 {{ displayReferralValue(form, 'amount') }} 元</p>
          <el-form-item label="付款状态" prop="payment_status"><el-select v-model="form.payment_status" @change="paymentChanged"><el-option label="未支付" value="unpaid" /><el-option label="已支付" value="paid" /></el-select></el-form-item>
          <el-form-item v-if="form.payment_status === 'paid'" label="付款日期" prop="payment_date"><el-date-picker v-model="form.payment_date" type="date" value-format="YYYY-MM-DD" placeholder="选择实际付款日期" /></el-form-item>
        </template>
        <template v-else>
          <div class="referral-form-grid">
            <el-form-item label="推广日期" prop="work_date"><el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" @change="checkDuplicates" /></el-form-item>
            <el-form-item label="推荐人姓名" prop="full_name"><el-input v-model="form.full_name" maxlength="255" @blur="checkDuplicates" /></el-form-item>
            <el-form-item label="推荐人微信" prop="wechat"><el-input v-model="form.wechat" maxlength="100" @blur="checkDuplicates" /></el-form-item>
            <el-form-item label="金额（元）" prop="amount"><el-input v-model="form.amount" inputmode="decimal" placeholder="请输入金额" /></el-form-item>
          </div>
          <el-alert v-if="duplicates.length" type="warning" :closable="false" title="同一日期、姓名和微信已有记录，建议打开已有记录补充；确认属于另一条记录时仍可保存。"><el-button v-for="row in duplicates" :key="row.id" link type="primary" @click="openDuplicate(row)">编辑 {{ row.full_name }} · {{ dateText(row.work_date) }}</el-button></el-alert>
          <div class="referral-entry-grid">
            <div class="referral-entry-heading" aria-hidden="true"><span>推广类型</span><span>说明</span><span>图片凭证</span></div>
            <div v-for="category in promotionCategories" :key="category.key" class="referral-entry-row" :data-evidence-category="category.key">
              <div class="referral-entry-type"><strong>{{ promotionLabels[category.key] }}</strong></div>
              <el-form-item :label="`${promotionLabels[category.key]}说明`" :prop="`${category.key}_description`">
                <el-input v-model="form[`${category.key}_description`]" type="textarea" :rows="3" maxlength="20000" placeholder="填写说明，也可直接粘贴截图" @paste="pasteDescription($event, category.key)" />
              </el-form-item>
              <el-form-item :label="category.label" :prop="`images_${category.key}`">
                <ReferralEvidenceCell :category="category" :images="images.filter(i => i.category === category.key)" :drafts="files.filter(i => i.category === category.key)" :disabled="imageDisabled" @files="queueFiles($event, category.key)" @remove="removeImage" @remove-draft="removeDraft" />
              </el-form-item>
            </div>
          </div>
          <el-form-item :label="qrCategory.label" prop="images_qr" class="referral-qr-row">
            <ReferralEvidenceCell :category="qrCategory" :images="images.filter(i => i.category === 'qr')" :drafts="files.filter(i => i.category === 'qr')" :disabled="imageDisabled" @files="queueFiles($event, 'qr')" @remove="removeImage" @remove-draft="removeDraft" />
          </el-form-item>
          <el-form-item label="备注" prop="remarks"><el-input v-model="form.remarks" type="textarea" :rows="2" maxlength="20000" /></el-form-item>
        </template>
      </AppForm>
    </div>
    <template #footer>
      <span v-if="files.length" class="referral-footer-hint" role="status">待上传 {{ files.length }} 张{{ continueAfterSave ? '，全部成功后继续新增' : '' }}</span>
      <el-button :disabled="saving" @click="closeEditor">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading || conflict" @click="save()">{{ files.some(i => i.error) ? '保存并重试图片' : '保存' }}</el-button>
      <el-button v-if="newSession && mode === 'record'" type="primary" plain :disabled="saving || loading || conflict" @click="save(true)">保存并继续新增</el-button>
    </template>
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
import { pasteReferralImages, queueReferralImages, releaseReferralDrafts, removeReferralDraft } from '@/utils/referralImages'
import ReferralEvidenceCell from './ReferralEvidenceCell.vue'
const emit = defineEmits(['saved'])
const visible = ref(false), saving = ref(false), loading = ref(false), mode = ref('record'), conflict = ref(false)
const formRef = ref(), bodyRef = ref(), files = ref([]), images = ref([]), duplicates = ref([])
const newSession = ref(false), continueAfterSave = ref(false)
const validating = ref(false)
const imageDisabled = computed(() => saving.value || loading.value || conflict.value || !visible.value)
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
const empty = () => ({ id: newDevelopmentId(), revision: 0, work_date: today(), full_name: '', wechat: '', amount: '', pull_description: '', moments_description: '', groups_description: '', remarks: '', payment_status: 'unpaid', payment_date: null })
const form = reactive(empty())
const promotionCategories = imageCategories.filter(category => category.key !== 'qr')
const qrCategory = imageCategories.find(category => category.key === 'qr')
const promotionLabels = { pull: '拉人', moments: '发圈', groups: '发群' }
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
  mode.value = newMode; clearDraftFiles(); duplicates.value = []; images.value = []; conflict.value = false; loading.value = false
  newSession.value = !row && newMode === 'record'; continueAfterSave.value = false
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
  if (loading.value || saving.value) return
  const seq = openSeq
  loading.value = true
  try {
    const record = await api.detail(form.id)
    if (seq === openSeq && visible.value) { applyRecord(record); conflict.value = false; formRef.value?.clearValidate(); emit('saved', form.id) }
  }
  catch (e) { if (seq === openSeq) ElMessage.error(e.message) } finally { if (seq === openSeq) loading.value = false }
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
function queueFiles(incoming, category) {
  if (imageDisabled.value) return
  const result = queueReferralImages(files.value, incoming, category, { createId: newDevelopmentId })
  files.value = result.items
  result.errors.forEach(message => ElMessage.warning(message))
}
function pasteDescription(event, category) { pasteReferralImages(event, incoming => queueFiles(incoming, category), { disabled: imageDisabled.value, preserveText: true }) }
function removeDraft(id) { if (!imageDisabled.value) files.value = removeReferralDraft(files.value, id) }
function clearDraftFiles() { releaseReferralDrafts(files.value); files.value = [] }
function handleError(e) { if (e.response?.status === 409 || e.status === 409) conflict.value = true; ElMessage.error(e.message) }
async function removeImage(image) {
  if (imageDisabled.value) return
  try { await ElMessageBox.confirm('确定删除这张图片？删除将立即保存并记录操作历史。', '删除图片', { type: 'warning' }) } catch { return }
  if (imageDisabled.value) return
  saving.value = true
  try {
    const record = await api.removeImage(form, image.id)
    // 图片删除立即保存，保留尚未提交的业务字段草稿。
    form.revision = record.revision; images.value = record.images || []; emit('saved', form.id)
  }
  catch (e) { handleError(e) } finally { saving.value = false }
}
async function save(continueAdding = continueAfterSave.value) {
  if (saving.value || validating.value || loading.value || conflict.value || !visible.value) return
  const seq = openSeq
  validating.value = true
  let valid
  try { valid = await formRef.value.validate().catch(() => false) }
  finally { validating.value = false }
  if (!valid || seq !== openSeq || !visible.value || loading.value || conflict.value) return
  saving.value = true
  let focusNext = false
  try {
    continueAfterSave.value = !!continueAdding && newSession.value && mode.value === 'record'
    if (mode.value === 'payment') {
      applyRecord(await api.payment(form.id, { revision: form.revision, payment_status: form.payment_status, payment_date: form.payment_date }))
    } else {
      const { payment_status, payment_date, ...payload } = form
      applyRecord(await api.save(payload))
      for (const item of [...files.value]) {
        try { applyRecord(await api.upload(form, item)); files.value = removeReferralDraft(files.value, item.id) }
        catch (e) { item.error = e.message; if (e.response?.status === 409 || e.status === 409) { conflict.value = true; break } }
      }
    }
    emit('saved', form.id)
    if (files.value.length) ElMessage.warning(`记录已保存，${files.value.length}张图片尚未上传，请查看错误并重试。`)
    else if (continueAfterSave.value) {
      const workDate = form.work_date
      duplicateController?.abort(); ++duplicateSeq; duplicates.value = []; images.value = []; clearDraftFiles()
      Object.assign(form, empty(), { work_date: workDate }); continueAfterSave.value = false; clearFieldSearch()
      await nextTick(); formRef.value?.clearValidate(); focusNext = true
      ElMessage.success('推荐拓展已保存，请继续登记下一位')
    } else { visible.value = false; ElMessage.success('推荐拓展已保存') }
  } catch (e) { await formRef.value?.applyServerErrors(e); handleError(e) }
  finally {
    saving.value = false
    if (focusNext) { await nextTick(); await locateDialogFieldByLabel('推荐人姓名') }
  }
}
function beforeClose(done) { if (!saving.value) done() }
function closeEditor() { if (!saving.value) visible.value = false }
function closed() { ++openSeq; duplicateController?.abort(); ++duplicateSeq; clearDraftFiles(); images.value = []; duplicates.value = []; continueAfterSave.value = false; clearFieldSearch() }
onBeforeUnmount(() => { duplicateController?.abort(); ++openSeq; clearDraftFiles() })
defineExpose({ open })
</script>

<style>
.referral-editor{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.referral-editor>.el-dialog__header,.referral-editor>.el-dialog__footer{flex-shrink:0}
.referral-editor>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.referral-editor>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc;display:flex;justify-content:flex-end;align-items:center;gap:8px;flex-wrap:wrap}
.referral-editor>.el-dialog__footer>.el-button+.el-button{margin-left:0}
.referral-footer-hint{margin-right:auto;font-size:12px;color:#64748b}
.referral-form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0 16px}
.referral-editor .el-alert{margin-bottom:16px}.referral-editor .el-date-editor,.referral-editor .el-select{width:100%;min-width:0}
.referral-entry-grid{border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}
.referral-entry-heading,.referral-entry-row{display:grid;grid-template-columns:96px minmax(140px,.7fr) minmax(0,1.3fr);gap:16px;padding:12px}
.referral-entry-heading{background:#f8fafc;font-size:13px;color:#475569;font-weight:600}
.referral-entry-row{border-top:1px solid #e2e8f0;align-items:start}
.referral-entry-type{display:flex;flex-direction:column;gap:8px;padding-top:8px;font-size:14px;color:#334155}
.referral-entry-type>span{font-size:12px;color:#64748b;line-height:1.5}
.referral-entry-row .el-form-item{min-width:0;margin-bottom:0}
.referral-entry-row .el-form-item__label{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.referral-entry-row .el-form-item__content{min-width:0}.referral-qr-row{margin-top:18px}
@media(max-width:800px){.referral-form-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.referral-entry-heading{display:none}.referral-entry-row{grid-template-columns:minmax(0,1fr);gap:12px}.referral-entry-type{flex-direction:row;align-items:center;padding-top:0}.referral-entry-row .el-form-item__label{position:static;width:auto;height:auto;margin:0 0 8px;overflow:visible;clip-path:none;white-space:normal}}
@media(max-width:640px){.referral-form-grid{grid-template-columns:1fr}.referral-editor .dialog-field-search-header{flex-wrap:wrap}.referral-editor .dialog-field-search-header__search{min-width:0;flex-basis:100%;width:100%}.referral-footer-hint{flex-basis:100%}}
</style>
