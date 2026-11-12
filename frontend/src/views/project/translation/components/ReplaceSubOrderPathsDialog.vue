<template>
  <DraggableFormDialog :model-value="modelValue" title="批量替换子订单路径"
    class="replace-suborder-paths-dialog" width="min(1050px, calc(100vw - 32px))" top="5vh" append-to-body
    :close-on-click-modal="!busy" :close-on-press-escape="!busy" :before-close="closeDialog"
    @update:model-value="$emit('update:modelValue', $event)">
    <AppForm :model="paths" label-width="110px">
      <el-form-item label="旧根路径" prop="oldRoot">
        <el-input v-model="paths.oldRoot" :disabled="busy" placeholder="例如 D:\原项目目录" />
      </el-form-item>
      <el-form-item label="新根路径" prop="newRoot">
        <el-input v-model="paths.newRoot" :disabled="busy" placeholder="例如 E:\迁移后目录" />
      </el-form-item>
    </AppForm>
    <p>替换当前母订单下所有匹配旧根路径的子订单，保留后面的目录、文件名和「同上一级订单」标记。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <template v-if="preview">
      <p role="status">将修改 {{ preview.changedCount }} 条，{{ preview.unchangedCount }} 条保持原路径。</p>
      <el-table v-if="preview.changedCount" :data="preview.changes" border max-height="350">
        <el-table-column prop="orderNo" label="子订单号" width="190" />
        <el-table-column prop="oldPath" label="原路径" min-width="300" />
        <el-table-column prop="newPath" label="新路径" min-width="300" />
      </el-table>
    </template>
    <template #footer>
      <el-button :disabled="busy" @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button :disabled="busy || !canPreview" :loading="busy && !preview" @click="run(false)">预览替换</el-button>
      <el-button type="primary" :disabled="busy || !preview?.changedCount" :loading="busy && !!preview" @click="run(true)">保存替换</el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { replaceSubOrderPaths } from '@/api/subOrders'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props = defineProps({ modelValue: Boolean, projectId: { type: String, required: true }, rootPath: String })
const emit = defineEmits(['update:modelValue', 'saved'])
const paths = reactive({ oldRoot: '', newRoot: '' })
const busy = ref(false)
const preview = ref(null)
const error = ref('')
const canPreview = computed(() => Boolean(paths.oldRoot.trim() && paths.newRoot.trim()))
function closeDialog(done) {
  if (!busy.value) done()
}

watch(() => props.modelValue, visible => {
  if (!visible) return
  paths.oldRoot = props.rootPath || ''
  paths.newRoot = ''
  preview.value = null
  error.value = ''
})
watch(paths, () => {
  preview.value = null
  error.value = ''
})

async function run(apply) {
  if (busy.value || !canPreview.value || (apply && !preview.value?.changedCount)) return
  const data = { ...paths }
  if (apply) data.previewToken = preview.value.previewToken
  else preview.value = null
  busy.value = true
  error.value = ''
  try {
    const result = await replaceSubOrderPaths(props.projectId, data)
    if (apply) {
      ElMessage.success(`已替换 ${result.changedCount} 条子订单路径`)
      emit('update:modelValue', false)
      emit('saved')
    } else {
      preview.value = result
    }
  } catch (cause) {
    preview.value = null
    error.value = getLocalizedErrorMessage(cause, '批量替换路径失败')
  } finally {
    busy.value = false
  }
}
</script>

<style>
.replace-suborder-paths-dialog { display: flex; flex-direction: column; max-height: 90vh; }
.replace-suborder-paths-dialog > .el-dialog__body { min-height: 0; overflow: auto; }
.replace-suborder-paths-dialog > .el-dialog__footer { flex-shrink: 0; border-top: 1px solid var(--el-border-color-lighter); }
</style>
