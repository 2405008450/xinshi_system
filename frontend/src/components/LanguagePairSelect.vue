<template>
  <div class="language-pair-select">
    <el-select-v2
      v-model="selectedPairs"
      :options="filteredLanguagePairOptions"
      multiple
      filterable
      clearable
      collapse-tags
      collapse-tags-tooltip
      :max-collapse-tags="2"
      :placeholder="placeholder"
      :filter-method="filterLanguagePairs"
      :loading="loading"
      :disabled="loading || loadingFailed"
      style="width: 100%"
      @visible-change="handleVisibleChange"
    />
    <div v-if="showHint" class="language-pair-select__hint">
      {{ hintText }}
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getLanguageVariants } from '@/api/projects'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '请选择一个或多个翻译方向'
  },
  showHint: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue'])

const languageVariants = ref([])
const searchKeyword = ref('')
const loading = ref(false)
const loadingFailed = ref(false)

const normalizeSearchText = (value) => String(value || '').toLocaleLowerCase().replace(/\s+/g, '')
const normalizeDirectionQuery = (value) => normalizeSearchText(value).replace(
  /翻译成为|翻译成|翻译为|转换成为|转换成|转换为|译成|译为|转成|转为|翻译|转换|->|=>|→|译|转|到|至/g,
  ''
)

const languagePairOptions = computed(() => {
  return languageVariants.value.flatMap((source) => (
    languageVariants.value
      .filter((target) => target.code !== source.code)
      .map((target) => {
        const value = `${source.label}→${target.label}`
        const sourceShortcuts = source.shortcuts || []
        const targetShortcuts = target.shortcuts || []
        return {
          label: value,
          value,
          searchText: normalizeSearchText([
            value,
            source.code,
            target.code,
            ...(source.aliases || []),
            ...(target.aliases || [])
          ].join('|')),
          directionSearchText: normalizeSearchText(
            sourceShortcuts.flatMap((sourceShortcut) => (
              targetShortcuts.map((targetShortcut) => `${sourceShortcut}${targetShortcut}`)
            )).join('|')
          )
        }
      })
  ))
})

const filteredLanguagePairOptions = computed(() => {
  const tokens = String(searchKeyword.value || '')
    .toLocaleLowerCase()
    .split(/[\s|/]+/)
    .map(normalizeSearchText)
    .filter(Boolean)
  if (!tokens.length) return languagePairOptions.value
  return languagePairOptions.value.filter((item) => (
    tokens.every((token) => {
      const normalizedToken = normalizeSearchText(token)
      const directionToken = normalizeDirectionQuery(token)
      return (
        item.searchText.includes(normalizedToken)
        || (
          directionToken
          && item.directionSearchText.includes(directionToken)
        )
      )
    })
  ))
})

const allowedLanguagePairSet = computed(() => (
  new Set(languagePairOptions.value.map((item) => item.value))
))

const hintText = computed(() => {
  if (loadingFailed.value) return '语种候选项加载失败，请刷新页面后重试'
  return '输入语种、地区或代码搜索，只能选择候选语言对'
})

const parseLanguagePairs = (value) => {
  if (!value) return []
  return [...new Set(
    String(value)
      .split(/[；;，,、\n]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  )]
}

const selectedPairs = computed({
  get: () => parseLanguagePairs(props.modelValue),
  set: (values) => {
    const normalized = [...new Set(
      (Array.isArray(values) ? values : [])
        .map((item) => String(item).trim())
        .filter((item) => allowedLanguagePairSet.value.has(item))
    )]
    emit('update:modelValue', normalized.join('；'))
  }
})

const filterLanguagePairs = (query) => {
  searchKeyword.value = query || ''
}

const handleVisibleChange = (visible) => {
  if (!visible) searchKeyword.value = ''
}

const loadLanguageVariants = async () => {
  loading.value = true
  loadingFailed.value = false
  try {
    const response = await getLanguageVariants()
    languageVariants.value = Array.isArray(response) ? response : []
    loadingFailed.value = languageVariants.value.length === 0
  } catch {
    languageVariants.value = []
    loadingFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(loadLanguageVariants)
</script>

<style scoped>
.language-pair-select {
  width: 100%;
}

.language-pair-select__hint {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}
</style>
