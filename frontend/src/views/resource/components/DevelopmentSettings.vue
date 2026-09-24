<template>
  <DraggableFormDialog v-model="visible" title="平台与选项维护" width="min(780px, calc(100vw - 32px))" top="5vh" class="development-dialog" destroy-on-close>
    <el-tabs v-model="tab">
      <el-tab-pane label="开拓平台" name="platform"><div v-for="group in categoryOptions" :key="group.value"><h3>{{ group.label }}</h3><el-button v-for="p in options.options.filter(p => p.kind === 'platform' && p.category === group.value)" :key="p.id" class="platform-chip" @click="edit(p)">{{ p.name }} · 情况说明</el-button><el-button plain @click="create('platform', group.value)">人工添加</el-button></div></el-tab-pane>
      <el-tab-pane label="对接账号" name="account"><el-tag v-for="a in options.options.filter(o => o.kind === 'account')" :key="a.id" class="platform-chip">{{ a.name }}</el-tag><el-button @click="create('account')">新增账号</el-button></el-tab-pane>
      <el-tab-pane label="语种/方言" name="language"><p>与人才总库共用语种目录。</p><el-button @click="create('language')">新增语种/方言</el-button></el-tab-pane>
    </el-tabs>
    <template #footer><el-button @click="visible = false">关闭</el-button></template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="editing" :title="editId ? `${form.name} · 情况说明` : '新增选项'" width="min(600px, calc(100vw - 32px))" append-to-body>
    <AppForm ref="formRef" :model="form" label-position="top" :rules="{name:[{required:true,whitespace:true,message:'请填写名称'}]}">
      <el-form-item label="名称" prop="name"><el-input v-model="form.name" :disabled="Boolean(editId)" maxlength="100" /></el-form-item>
      <el-form-item v-if="form.kind === 'language'" label="类型"><el-select v-model="form.language_type"><el-option label="语种" value="language" /><el-option label="方言" value="dialect" /></el-select></el-form-item>
      <el-form-item v-if="form.kind === 'platform'" label="平台情况说明"><el-input v-model="form.description" type="textarea" :rows="6" maxlength="5000" /></el-form-item>
    </AppForm>
    <template #footer><el-button @click="editing = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { developmentApi as api } from '@/api/resourceDevelopment'
import { categoryOptions } from '@/utils/resourceDevelopment'
defineProps({ options: { type: Object, required: true } }); const emit = defineEmits(['saved'])
const visible = ref(false), editing = ref(false), saving = ref(false), tab = ref('platform'), editId = ref(null), formRef = ref(null)
const form = reactive({ kind: 'platform', category: '', name: '', description: '', revision: 0, language_type: 'language' })
function create(kind, category = '') { editId.value = null; Object.assign(form, { kind, category, name: '', description: '', revision: 0, language_type: 'language' }); editing.value = true }
function edit(p) { editId.value = p.id; Object.assign(form, p); editing.value = true }
async function save() {
  if (!await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try {
    if (form.kind === 'language') await api.addLanguage({ label: form.name, language_type: form.language_type })
    else await api.saveOption({ kind: form.kind, category: form.category, name: form.name, description: form.description, revision: form.revision }, editId.value)
    editing.value = false; emit('saved'); ElMessage.success('选项已保存')
  } catch (e) { ElMessage.error(e.message) } finally { saving.value = false }
}
defineExpose({ open: () => { visible.value = true }, edit })
</script>
