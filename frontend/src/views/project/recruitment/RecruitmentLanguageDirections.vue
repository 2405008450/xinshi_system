<template>
  <div class="direction-editor">
    <div v-for="(item, index) in localValue" :key="index" class="direction-row">
      <el-select v-model="item.directionType" style="width: 126px" @change="handleTypeChange(item)">
        <el-option label="单语种" value="single" />
        <el-option label="翻译成" value="translation" />
      </el-select>
      <el-select v-model="item.sourceLanguageId" filterable placeholder="选择语种/方言" style="flex: 1" @change="emitValue">
        <el-option v-for="language in languages" :key="language.id" :label="language.label" :value="language.id">
          <span>{{ language.label }}</span><el-tag v-if="language.isCustom" size="small" type="warning" class="new-tag">新</el-tag>
        </el-option>
      </el-select>
      <template v-if="item.directionType === 'translation'">
        <span>翻译成</span>
        <el-select v-model="item.targetLanguageId" filterable placeholder="选择目标语种" style="flex: 1" @change="emitValue">
          <el-option v-for="language in languages" :key="language.id" :label="language.label" :value="language.id" :disabled="language.id === item.sourceLanguageId">
            <span>{{ language.label }}</span><el-tag v-if="language.isCustom" size="small" type="warning" class="new-tag">新</el-tag>
          </el-option>
        </el-select>
      </template>
      <el-button type="danger" link @click="remove(index)">删除</el-button>
    </div>
    <div class="direction-actions">
      <el-button @click="add">新增方向</el-button>
      <el-popover v-model:visible="createVisible" trigger="click" placement="bottom-end" :width="320">
        <template #reference><el-button>新增共享语种</el-button></template>
        <el-form @submit.prevent>
          <el-form-item label="语种名称"><el-input v-model="newLabel" maxlength="100" placeholder="例如：吴语（上海话）" @keyup.enter="createLanguage" /></el-form-item>
          <div class="create-actions"><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="creating" @click="createLanguage">添加</el-button></div>
        </el-form>
      </el-popover>
    </div>
    <div class="hint">支持单个语种、多个方向及“方言翻译成普通话”；自定义语种会进入共享目录并标记为“新”。</div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'

const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue'])
const languages = ref([])
const localValue = ref([])
const createVisible = ref(false)
const creating = ref(false)
const newLabel = ref('')
let syncing = false

const normalize = (items) => (items || []).map((item) => ({
  directionType: item.directionType || 'single',
  sourceLanguageId: item.sourceLanguageId || '',
  targetLanguageId: item.targetLanguageId || '',
}))

watch(() => props.modelValue, (value) => {
  if (syncing) return
  localValue.value = normalize(value)
}, { immediate: true, deep: true })

const emitValue = () => {
  syncing = true
  emit('update:modelValue', normalize(localValue.value))
  queueMicrotask(() => { syncing = false })
}
const add = () => { localValue.value.push({ directionType: 'single', sourceLanguageId: '', targetLanguageId: '' }); emitValue() }
const remove = (index) => { localValue.value.splice(index, 1); emitValue() }
const handleTypeChange = (item) => { if (item.directionType === 'single') item.targetLanguageId = ''; emitValue() }

const load = async () => {
  try { languages.value = await getProjectLanguages() } catch { ElMessage.error('共享语种加载失败') }
}
const createLanguage = async () => {
  const label = newLabel.value.trim()
  if (!label) return ElMessage.warning('请输入语种名称')
  creating.value = true
  try {
    const created = await createProjectLanguage(label)
    languages.value.push(created)
    languages.value.sort((a, b) => Number(a.isCustom) - Number(b.isCustom) || a.label.localeCompare(b.label, 'zh-CN'))
    newLabel.value = ''
    createVisible.value = false
    ElMessage.success('语种已添加到共享目录')
  } catch (error) { ElMessage.error(error?.response?.data?.detail || '新增语种失败') }
  finally { creating.value = false }
}
onMounted(load)
</script>

<style scoped>
.direction-editor { width: 100%; }
.direction-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.direction-actions, .create-actions { display: flex; gap: 8px; justify-content: flex-end; }
.hint { margin-top: 5px; color: var(--el-text-color-secondary); font-size: 12px; }
.new-tag { float: right; margin-left: 8px; }
@media (max-width: 720px) { .direction-row { align-items: stretch; flex-direction: column; } }
</style>
