<template>
  <DraggableFormDialog v-model="visible" title="平台与选项维护" width="min(780px, calc(100vw - 32px))" top="5vh" class="development-dialog" destroy-on-close>
    <el-tabs v-model="tab">
      <el-tab-pane label="开拓平台" name="platform"><div v-for="group in categoryOptions" :key="group.value"><h3>{{ group.label }}</h3><el-button v-for="p in options.options.filter(p => p.kind === 'platform' && p.category === group.value)" :key="p.id" class="platform-chip" @click="edit(p)">{{ p.name }} · 情况说明</el-button><el-button plain @click="create('platform', group.value)">人工添加</el-button></div></el-tab-pane>
      <el-tab-pane label="交换账号" name="account"><el-tag v-for="a in options.options.filter(o => o.kind === 'account')" :key="a.id" class="platform-chip">{{ a.name }}</el-tag><el-button @click="create('account')">新增账号</el-button></el-tab-pane>
      <el-tab-pane label="语种/方言" name="language"><p>与人才总库共用语种目录。</p><el-button @click="create('language')">新增语种/方言</el-button></el-tab-pane>
    </el-tabs>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
  <ChannelDescriptionEditor ref="descriptionRef" :can-write="options.can_write" @saved="saved" />
  <ChannelEditor ref="channelRef" :options="options" @saved="saved" />
  <DraggableFormDialog v-model="editing" title="新增选项" width="min(600px, calc(100vw - 32px))" class="development-dialog" append-to-body>
    <AppForm ref="formRef" :model="form" label-position="top" :rules="{name:[{required:true,whitespace:true,message:'请填写名称'}]}">
      <el-form-item label="名称" prop="name"><el-input v-model="form.name" maxlength="100" /></el-form-item>
      <el-form-item v-if="form.kind === 'language'" label="类型"><el-select v-model="form.language_type"><el-option label="语种" value="language" /><el-option label="方言" value="dialect" /></el-select></el-form-item>
    </AppForm>
    <template #footer><el-button @click="editing = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions } from '@/utils/resourceDevelopment'
import ChannelDescriptionEditor from './ChannelDescriptionEditor.vue'
import ChannelEditor from './ChannelEditor.vue'
const props = defineProps({ options: { type: Object, required: true } }); const emit = defineEmits(['saved'])
const currentOptions = ref(null), options = computed(() => currentOptions.value || props.options)
const visible = ref(false), editing = ref(false), saving = ref(false), tab = ref('platform'), formRef = ref(null), descriptionRef = ref(null), channelRef = ref(null)
const form = reactive({ kind: 'platform', category: '', name: '', description: '', revision: 0, language_type: 'language' })
function create(kind, category = '') { if (kind === 'platform') return channelRef.value.open(undefined, category); Object.assign(form, { kind, category, name: '', description: '', revision: 0, language_type: 'language' }); editing.value = true }
function edit(p) { if (p) return descriptionRef.value.open(p) }
async function saved() { emit('saved'); try { currentOptions.value = await api.options() } catch (error) { ElMessage.error(error.message) } }
async function open() { try { currentOptions.value = await api.options(); visible.value = true } catch (error) { ElMessage.error(error.message) } }
async function addPlatform() { await open(); if (visible.value) { tab.value = 'platform'; create('platform', 'national') } }
async function save() {
  if (!await formRef.value.validate().catch(() => false)) return
  if (saving.value) return
  saving.value = true
  try {
    if (form.kind === 'language') await api.addLanguage({ label: form.name, language_type: form.language_type })
    else await api.saveOption({ kind: form.kind, category: form.category, name: form.name, description: form.description, revision: form.revision })
    editing.value = false; await saved(); ElMessage.success('选项已保存')
  } catch (e) {
        await formRef.value?.applyServerErrors(e)
 ElMessage.error(e.message) } finally { saving.value = false }
}
defineExpose({ open, edit, addPlatform })
</script>
