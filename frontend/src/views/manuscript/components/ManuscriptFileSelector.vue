<template>
  <div class="file-selector">
    <div class="file-selector__summary">
      <span>{{ modelValue.length ? `已选择 ${modelValue.length} 个文件` : '尚未选择派稿文件' }}</span>
      <el-popover :disabled="disabled" trigger="click" placement="bottom-start" width="min(720px, calc(100vw - 32px))" @show="openBrowser">
        <template #reference><el-button type="primary" link :disabled="disabled">选择文件</el-button></template>
        <div class="file-browser">
          <div class="file-browser__toolbar">
            <el-button :disabled="!currentDirectory" @click="goUp">返回上级</el-button>
            <span :title="currentDirectory">/{{ currentDirectory || '' }}</span>
            <el-button :loading="loading" @click="loadDirectory">刷新</el-button>
          </div>
          <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
          <el-table v-else v-loading="loading" :data="items" size="small" border max-height="360">
            <el-table-column width="52" align="center">
              <template #default="{ row }">
                <el-checkbox v-if="row.selectable" :model-value="isSelected(row.relative_path)" @change="toggle(row, $event)" />
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="280">
              <template #default="{ row }">
                <el-button v-if="row.is_directory" type="primary" link @click="enterDirectory(row)">📁 {{ row.name }}</el-button>
                <span v-else :class="{ 'is-disabled': !row.selectable }" :title="row.unavailable_reason || row.relative_path">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="110"><template #default="{ row }">{{ formatSize(row.file_size) }}</template></el-table-column>
            <el-table-column label="修改时间" width="170"><template #default="{ row }">{{ formatTime(row.modified_at) }}</template></el-table-column>
          </el-table>
          <el-alert v-if="truncated" title="当前目录项目过多，仅显示前 500 项，请整理目录后再选择" type="warning" :closable="false" show-icon />
        </div>
      </el-popover>
    </div>
    <div v-if="modelValue.length" class="file-selector__tags">
      <el-tag v-for="file in modelValue" :key="file.relative_path" :closable="!disabled" @close="remove(file.relative_path)">{{ file.relative_path }}</el-tag>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getManuscriptDispatchFiles } from '@/api/manuscriptArrangements'

const props = defineProps({
  projectId: { type: [String, Number], required: true },
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])
const loading = ref(false)
const items = ref([])
const currentDirectory = ref('')
const truncated = ref(false)
const errorMessage = ref('')

function selectedPaths() { return new Set(props.modelValue.map((item) => item.relative_path)) }
function isSelected(path) { return selectedPaths().has(path) }
function toggle(row, selected) {
  const next = props.modelValue.filter((item) => item.relative_path !== row.relative_path)
  if (selected) next.push({ relative_path: row.relative_path })
  emit('update:modelValue', next)
}
function remove(path) { emit('update:modelValue', props.modelValue.filter((item) => item.relative_path !== path)) }
async function loadDirectory() {
  loading.value = true; errorMessage.value = ''
  try {
    const response = await getManuscriptDispatchFiles(props.projectId, { relative_directory: currentDirectory.value })
    items.value = response.items || []; truncated.value = Boolean(response.truncated)
  } catch (error) {
    items.value = []; truncated.value = false; errorMessage.value = error.detail || '读取派稿目录失败'
  } finally { loading.value = false }
}
function openBrowser() { currentDirectory.value = ''; loadDirectory() }
function enterDirectory(row) { currentDirectory.value = row.relative_path; loadDirectory() }
function goUp() { currentDirectory.value = currentDirectory.value.split('/').slice(0, -1).join('/'); loadDirectory() }
function formatSize(value) {
  if (value === null || value === undefined) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
</script>

<style scoped>
.file-selector { width: 100%; }
.file-selector__summary { display: flex; align-items: center; justify-content: space-between; min-height: 32px; padding: 0 10px; border: 1px solid var(--el-border-color); border-radius: 4px; }
.file-selector__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.file-browser { display: flex; flex-direction: column; gap: 8px; }
.file-browser__toolbar { display: flex; align-items: center; gap: 8px; }
.file-browser__toolbar span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.is-disabled { color: var(--el-text-color-disabled); }
</style>
