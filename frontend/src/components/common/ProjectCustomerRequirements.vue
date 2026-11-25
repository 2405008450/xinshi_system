<template>
  <div class="requirement-actions" data-dialog-field-search-label="同步客户要求">
    <el-button :disabled="!project.clientId || disabled" :loading="loading"
      title="从客户对应项目类型的通用要求带入最新内容" @click="applyLatest">带入客户要求</el-button>
    <el-button v-if="canWriteClient" :disabled="!project.clientId || !project.id || disabled" @click="openPreview">
      同步要求至客户管理…
    </el-button>
    <small v-if="!project.clientId">选择已有客户后可带入要求。</small>
    <small v-else-if="canWriteClient && !project.id">保存项目后可回传要求。</small>
    <DraggableFormDialog v-model="visible" append-to-body title="同步要求至客户管理" class="requirement-sync-dialog"
      width="min(680px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="beforeClose">
      <p>同步至客户管理 → {{ requirementModules[module].label }} → 通用要求。可先编辑；与通用要求最新内容不同时新增历史，空白项不回传。</p>
      <AppForm :model="draft" label-position="top" :disabled="saving">
        <el-form-item v-for="(label, field) in fields" :key="field" :label="label">
          <el-input v-model="draft[field]" type="textarea" :rows="3" maxlength="10000" />
        </el-form-item>
      </AppForm>
      <template #footer>
        <el-button :disabled="saving" @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!hasContent" @click="save">确认同步</el-button>
      </template>
    </DraggableFormDialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { hasPermission } from '@/utils/permission'
import { projectRequirementFields, requirementModules, requirementPath } from '@/utils/customerRequirements'

const props = defineProps({ module: { type: String, required: true }, project: { type: Object, required: true }, disabled: Boolean })
const emit = defineEmits(['apply'])
const fields = computed(() => projectRequirementFields(props.module))
const canWriteClient = hasPermission('clients:write')
const draft = ref({})
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const hasContent = computed(() => Object.values(draft.value).some(value => value.trim()))
let source

async function applyLatest() {
  const { clientId, id } = props.project
  loading.value = true
  try {
    const { values } = await api.get(requirementPath(clientId, props.module), { params: { latest: true } })
    if (props.project.clientId !== clientId || props.project.id !== id) return
    const selected = Object.fromEntries(Object.entries(values).filter(([field]) => Object.hasOwn(fields.value, field)))
    if (!Object.keys(selected).length) return ElMessage.info('客户档案暂无此类要求')
    emit('apply', selected)
    ElMessage.success('已带入最新要求，保存项目后生效')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '读取客户要求失败'))
  } finally {
    loading.value = false
  }
}

function openPreview() {
  source = { clientId: props.project.clientId, projectId: props.project.id }
  draft.value = Object.fromEntries(Object.keys(fields.value).map(key => [key, props.project[key] || '']))
  visible.value = true
}

function beforeClose(done) {
  if (!saving.value) done()
}

async function save() {
  saving.value = true
  try {
    const { added } = await api.post(requirementPath(source.clientId, props.module), {
      project_id: source.projectId, values: draft.value,
    })
    visible.value = false
    ElMessage.success(added ? `已新增 ${added} 条客户要求` : '与客户档案最新内容一致，无需新增')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '同步客户要求失败'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.requirement-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.requirement-actions > .el-button { margin-left: 0; }
:global(.requirement-sync-dialog) { display: flex; flex-direction: column; max-height: 90vh; overflow: hidden; }
:global(.requirement-sync-dialog .el-dialog__body) { flex: 1; min-height: 0; overflow-y: auto; }
:global(.requirement-sync-dialog .el-dialog__footer) { flex-shrink: 0; border-top: 1px solid var(--el-border-color-lighter); }
</style>
