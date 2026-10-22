<template>
  <DraggableFormDialog v-model="visible" title="标注项目 · 默认参与人" width="min(680px, calc(100vw - 32px))" top="8vh" append-to-body destroy-on-close class="chat-default-participants" @open="load">
    <p class="chat-default-participants__hint">此名单由所有账号共用，仅用于新发起的标注会话。发起人自动加入，已有会话的参与人保持不变。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <AppForm ref="formRef" :model="form" v-loading="loading" @submit.prevent="save">
      <el-form-item label="搜索人员"><el-input v-model="keyword" clearable placeholder="姓名、账号、部门" /></el-form-item>
      <div class="chat-default-participants__tools"><span>已选择 {{ form.userIds.length }} 人</span><el-button link :disabled="!canManage" @click="selectVisible">选择搜索结果</el-button><el-button link :disabled="!canManage" @click="form.userIds = []">清空</el-button></div>
      <el-form-item label="全体人员" prop="userIds">
        <el-checkbox-group v-model="form.userIds" class="chat-default-participants__users" :disabled="!canManage">
          <el-checkbox v-for="user in filteredUsers" :key="user.id" :value="user.id" :disabled="!user.canParticipate" :title="user.canParticipate ? user.username : '该账号没有项目沟通权限'">{{ user.name }}<small>{{ user.department || user.username }}{{ user.canParticipate ? '' : ' · 无项目沟通权限' }}</small></el-checkbox>
        </el-checkbox-group>
      </el-form-item>
    </AppForm>
    <template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading || !loaded || !canManage" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import AppForm from '@/components/common/AppForm.vue'
import { annotationChatRequest } from '@/api/projectChat'
import { matchesSearch } from '@/utils/searchMatching'
const visible = defineModel({ type: Boolean, default: false })
const form = reactive({ userIds: [] }), users = ref([]), keyword = ref(''), formRef = ref()
const loading = ref(false), saving = ref(false), loaded = ref(false), canManage = ref(false), error = ref('')
let controller, generation = 0
const filteredUsers = computed(() => users.value.filter(user => matchesSearch(`${user.name} ${user.username} ${user.department}`, keyword.value)))
function selectVisible() { form.userIds = [...new Set([...form.userIds, ...filteredUsers.value.filter(user => user.canParticipate).map(user => user.id)])] }
async function load() {
  controller?.abort(); controller = new AbortController(); const version = ++generation
  loading.value = true; loaded.value = false; error.value = ''; keyword.value = ''
  try {
    const data = await annotationChatRequest('', 'default-participants', { signal: controller.signal })
    if (version !== generation) return
    users.value = data.users; form.userIds = data.userIds; canManage.value = data.canManage; loaded.value = true
  } catch (e) {
    if (version === generation && e.code !== 'ERR_CANCELED') {
      error.value = e.response?.status === 404
        ? '默认参与人功能尚未在后端启用，请完成服务更新后重试。'
        : e.detail || e.message || '加载失败'
    }
  }
  finally { if (version === generation) loading.value = false }
}
async function save() {
  if (!loaded.value || !canManage.value || saving.value) return
  if (!await formRef.value.validate().catch(() => false)) return
  saving.value = true; error.value = ''
  try { await annotationChatRequest('', 'default-participants', { method: 'put', data: { userIds: form.userIds } }); ElMessage.success('默认参与人已保存'); visible.value = false }
  catch (e) { error.value = e.detail || e.message || '保存失败' }
  finally { saving.value = false }
}
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>
<style>
.chat-default-participants{display:flex;flex-direction:column;max-height:84vh;overflow:hidden}
.chat-default-participants>.el-dialog__header,.chat-default-participants>.el-dialog__footer{flex:none}
.chat-default-participants>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}
.chat-default-participants>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}
.chat-default-participants__hint{font-size:12px;color:#64748b;line-height:1.7}
.chat-default-participants__tools{display:flex;gap:12px;align-items:center;margin:10px 0;font-size:12px}
.chat-default-participants__users{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;width:100%}
.chat-default-participants__users .el-checkbox{height:auto;min-height:36px;margin:0;white-space:normal}
.chat-default-participants__users small{display:block;color:#94a3b8;font-size:11px}
@media(max-width:600px){.chat-default-participants__users{grid-template-columns:1fr}}
</style>
