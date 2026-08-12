<template>
  <div class="language-pair-select">
    <div class="language-pair-select__row">
      <el-select
        v-model="selectedPairs"
        multiple
        filterable
        clearable
        collapse-tags
        collapse-tags-tooltip
        :max-collapse-tags="2"
        :placeholder="placeholder"
        :loading="loading"
        :disabled="loading || loadingFailed"
        style="width: 100%"
      >
        <el-option
          v-for="item in languagePairOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        >
          <span>{{ item.label }}</span>
          <el-tag v-if="item.isCustom" size="small" type="warning" class="new-language-tag">新</el-tag>
        </el-option>
      </el-select>
      <el-popover v-model:visible="createVisible" trigger="click" placement="bottom-end" :width="300">
        <template #reference>
          <el-button :disabled="loading" title="新增共享语种">新增语种</el-button>
        </template>
        <el-form @submit.prevent>
          <el-form-item label="语种名称">
            <el-input v-model="newLanguageLabel" maxlength="100" placeholder="例如：吴语（上海话）" @keyup.enter="handleCreateLanguage" />
          </el-form-item>
          <div class="create-actions">
            <el-button @click="createVisible = false">取消</el-button>
            <el-button type="primary" :loading="creating" @click="handleCreateLanguage">添加</el-button>
          </div>
        </el-form>
      </el-popover>
    </div>
    <div v-if="showHint" class="language-pair-select__hint">{{ hintText }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请选择一个或多个翻译方向' },
  showHint: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])
const languages = ref([])
const loading = ref(false)
const loadingFailed = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const newLanguageLabel = ref('')

const parseLanguagePairs = (value) => {
  if (!value) return []
  return [...new Set(String(value).split(/[；;，,、\n]+/).map((item) => item.trim()).filter(Boolean))]
}

const languagePairOptions = computed(() => {
  const generated = languages.value.flatMap((source) => languages.value
    .filter((target) => target.id !== source.id)
    .map((target) => ({
      label: `${source.label}→${target.label}`,
      value: `${source.label}→${target.label}`,
      isCustom: source.isCustom || target.isCustom,
    })))
  const known = new Set(generated.map((item) => item.value))
  const legacy = parseLanguagePairs(props.modelValue)
    .filter((value) => !known.has(value))
    .map((value) => ({ label: value, value, isCustom: true }))
  return [...legacy, ...generated]
})

const allowedLanguagePairSet = computed(() => new Set(languagePairOptions.value.map((item) => item.value)))
const selectedPairs = computed({
  get: () => parseLanguagePairs(props.modelValue),
  set: (values) => {
    const normalized = [...new Set((values || []).map((item) => String(item).trim())
      .filter((item) => allowedLanguagePairSet.value.has(item)))]
    emit('update:modelValue', normalized.join('；'))
  },
})

const hintText = computed(() => loadingFailed.value
  ? '语种候选项加载失败，请刷新页面后重试'
  : '语种目录由笔译、口译和标注项目共享；自定义语种标记为“新”')

const loadLanguages = async () => {
  loading.value = true
  loadingFailed.value = false
  try {
    languages.value = await getProjectLanguages()
    loadingFailed.value = languages.value.length === 0
  } catch {
    languages.value = []
    loadingFailed.value = true
  } finally {
    loading.value = false
  }
}

const handleCreateLanguage = async () => {
  const label = newLanguageLabel.value.trim()
  if (!label) return ElMessage.warning('请输入语种名称')
  creating.value = true
  try {
    const created = await createProjectLanguage(label)
    languages.value.push(created)
    languages.value.sort((a, b) => Number(a.isCustom) - Number(b.isCustom) || a.label.localeCompare(b.label, 'zh-CN'))
    newLanguageLabel.value = ''
    createVisible.value = false
    ElMessage.success('语种已添加到共享目录')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '新增语种失败')
  } finally {
    creating.value = false
  }
}

onMounted(loadLanguages)
</script>

<style scoped>
.language-pair-select,
.language-pair-select__row { width: 100%; }
.language-pair-select__row { display: flex; gap: 8px; align-items: flex-start; }
.language-pair-select__hint { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.4; }
.new-language-tag { float: right; margin-left: 8px; }
.create-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
