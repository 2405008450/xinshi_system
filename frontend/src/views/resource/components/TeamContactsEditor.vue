<template>
  <DraggableFormDialog ref="dialogRef" v-model="visible" width="min(800px, calc(100vw - 32px))" top="5vh" class="team-form-dialog team-contacts-dialog" append-to-body destroy-on-close :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="编辑团队对接人" placeholder="搜索字段，如昵称" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <el-alert v-if="!canViewContacts" title="联系方式仅超级管理员可查看和修改；已有联系方式会保留。" type="info" :closable="false" show-icon />
      <AppForm ref="formRef" :model="form" label-position="top">
        <section v-for="(contact, index) in form.contacts" :key="contact.id || contact._draftKey" class="team-contact-section form-section" data-dialog-field-search-group>
          <div class="team-contact-section-heading"><h3 data-dialog-field-search-group-title>对接人{{ index + 1 }}</h3><el-button link type="danger" :disabled="!canViewContacts && Boolean(contact.contact_info)" @click="removeContact(index)">移除对接人{{ index + 1 }}</el-button></div>
          <div class="team-form-grid">
            <el-form-item label="姓名" :prop="`contacts.${index}.name`" :rules="[{ validator: (_rule, _value, done) => validateIdentity(contact, done), trigger: 'blur' }]"><el-input v-model="contact.name" maxlength="100" placeholder="填写姓名，或在右侧填写昵称" /></el-form-item>
            <el-form-item label="昵称" :prop="`contacts.${index}.nickname`"><el-input v-model="contact.nickname" maxlength="100" /></el-form-item>
            <el-form-item label="联系方式" :prop="`contacts.${index}.contact_info`" class="team-wide">
              <el-input v-if="canViewContacts" v-model="contact.contact_info" type="textarea" :rows="2" maxlength="1000" show-word-limit placeholder="可填写电话、微信、邮箱等，多种方式可换行填写" />
              <SensitiveContactValue v-else :value="contact.contact_info" restricted />
            </el-form-item>
          </div>
        </section>
      </AppForm>
      <el-button :disabled="form.contacts.length >= 3" @click="addContact">增加对接人（{{ form.contacts.length }}/3）</el-button>
    </div>
    <template #footer><span class="team-contact-footer-hint">确定后回填表单，保存团队时生效</span><el-button @click="dialogRef.handleClose()">取消</el-button><el-button type="primary" @click="confirm">确定</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import { nextTick, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { cleanTeamContacts, emptyTeamContact } from '@/utils/teamResources'

const props = defineProps({ canViewContacts: { type: Boolean, default: false } })
const emit = defineEmits(['confirmed'])
const visible = ref(false), dialogRef = ref(null), formRef = ref(null), bodyRef = ref(null)
const form = reactive({ contacts: [] })
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
let original = '', draftSequence = 0
const signature = () => JSON.stringify(cleanTeamContacts(form.contacts, props.canViewContacts))
function addContact() { if (form.contacts.length < 3) form.contacts.push({ ...emptyTeamContact(), _draftKey: ++draftSequence }) }
function removeContact(index) { form.contacts.splice(index, 1); if (!form.contacts.length) addContact() }
async function open(contacts) {
  form.contacts = (contacts || []).map(contact => ({ ...emptyTeamContact(), ...contact, _draftKey: ++draftSequence }))
  if (!form.contacts.length) addContact()
  original = signature(); clearFieldSearch(); visible.value = true
  await nextTick(); formRef.value?.clearValidate()
}
function validateIdentity(contact, done) {
  const used = contact.id || contact.name.trim() || contact.nickname.trim() || (props.canViewContacts && contact.contact_info.trim())
  done(used && !contact.name.trim() && !contact.nickname.trim() ? new Error('请填写对接人姓名或昵称') : undefined)
}
async function beforeClose(done) {
  if (signature() !== original) {
    try { await ElMessageBox.confirm('对接人修改尚未回填，确定放弃吗？', '放弃修改', { type: 'warning' }) } catch { return }
  }
  done()
}
async function confirm() {
  if (!await formRef.value.validate().catch(() => false)) return
  emit('confirmed', cleanTeamContacts(form.contacts)); visible.value = false
}
defineExpose({ open })
</script>

<style>
.team-contact-section { margin-bottom:20px; }
.team-contact-section-heading { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.team-contact-section-heading h3 { margin:0; font-size:15px; }
.team-contact-footer-hint { color:var(--el-text-color-secondary); font-size:12px; margin-right:12px; }
@media(max-width:640px) { .team-contact-footer-hint { display:block; margin:0 0 10px; } }
</style>
