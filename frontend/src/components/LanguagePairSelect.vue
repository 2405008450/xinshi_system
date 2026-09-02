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
        :filter-method="filterLanguagePairs"
        :loading="loading"
        :disabled="loading || loadingFailed"
        style="width: 100%"
        @visible-change="handleVisibleChange"
      >
        <el-option
          v-for="item in filteredLanguagePairOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        >
          <span>{{ item.label }}</span>
          <span v-if="item.shortLabel" class="language-pair-shortcut">{{ item.shortLabel }}</span>
          <el-tag v-if="item.isCustom" size="small" type="warning" class="new-language-tag">新</el-tag>
        </el-option>
      </el-select>
      <el-popover
        v-model:visible="createVisible"
        trigger="click"
        placement="bottom-end"
        :width="520"
        popper-class="language-pair-create-popper"
      >
        <template #reference>
          <el-button :disabled="loading" title="新增翻译方向">新增方向</el-button>
        </template>
        <AppForm class="direction-create-form" label-position="top" @submit.prevent>
          <div class="direction-create-fields">
            <el-form-item label="原文语种">
              <el-select
                v-model="newDirection.source"
                filterable
                allow-create
                default-first-option
                clearable
                :loading="creating"
                placeholder="选择或输入原文语种"
              >
                <el-option v-for="language in languages" :key="language.id" :label="language.label" :value="language.label" />
              </el-select>
            </el-form-item>
            <span class="direction-create-arrow" aria-hidden="true">→</span>
            <el-form-item label="译文语种">
              <el-select
                v-model="newDirection.target"
                filterable
                allow-create
                default-first-option
                clearable
                :loading="creating"
                placeholder="选择或输入译文语种"
              >
                <el-option
                  v-for="language in languages"
                  :key="language.id"
                  :label="language.label"
                  :value="language.label"
                  :disabled="isSameLanguage(language.label, newDirection.source)"
                />
              </el-select>
            </el-form-item>
          </div>
          <div class="create-actions">
            <el-button :disabled="creating" @click="handleCreateCancel">取消</el-button>
            <el-button type="primary" :loading="creating" @click="handleCreateDirection">添加方向</el-button>
          </div>
        </AppForm>
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
const searchKeyword = ref('')
const loading = ref(false)
const loadingFailed = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const newDirection = ref({ source: '', target: '' })

// 常用笔译方向固定前置；同一语种对按“简中译外语、外语译简中”相邻排列。
const COMMON_LANGUAGE_PAIR_CODES = [
  ['zh-CN', 'en-US'],
  ['en-US', 'zh-CN'],
  ['zh-CN', 'en-GB'],
  ['en-GB', 'zh-CN'],
  ['zh-CN', 'ja-JP'],
  ['ja-JP', 'zh-CN'],
  ['zh-CN', 'ko-KR'],
  ['ko-KR', 'zh-CN'],
  ['zh-CN', 'zh-TW'],
  ['zh-TW', 'zh-CN'],
  ['zh-CN', 'zh-HK'],
  ['zh-HK', 'zh-CN'],
  ['zh-CN', 'fr-FR'],
  ['fr-FR', 'zh-CN'],
  ['zh-CN', 'de-DE'],
  ['de-DE', 'zh-CN'],
  ['zh-CN', 'es-419'],
  ['es-419', 'zh-CN'],
  ['zh-CN', 'es-ES'],
  ['es-ES', 'zh-CN'],
  ['zh-CN', 'pt-BR'],
  ['pt-BR', 'zh-CN'],
  ['zh-CN', 'ru-RU'],
  ['ru-RU', 'zh-CN'],
  ['zh-CN', 'ar-MSA'],
  ['ar-MSA', 'zh-CN'],
  ['zh-CN', 'it-IT'],
  ['it-IT', 'zh-CN'],
  ['zh-CN', 'vi-VN'],
  ['vi-VN', 'zh-CN'],
  ['zh-CN', 'th-TH'],
  ['th-TH', 'zh-CN'],
  ['zh-CN', 'id-ID'],
  ['id-ID', 'zh-CN'],
  ['zh-CN', 'ms-MY'],
  ['ms-MY', 'zh-CN'],
]
const COMMON_LANGUAGE_PAIR_RANK = new Map(
  COMMON_LANGUAGE_PAIR_CODES.map(([sourceCode, targetCode], index) => (
    [`${sourceCode}→${targetCode}`, index]
  ))
)

const parseLanguagePairs = (value) => {
  if (!value) return []
  return [...new Set(String(value).split(/[；;，,、\n]+/).map((item) => item.trim()).filter(Boolean))]
}

const normalizeLanguageLabel = (value) => String(value || '').trim().replace(/\s+/g, ' ')
const comparableLanguageLabel = (value) => normalizeLanguageLabel(value).toLocaleLowerCase()
const isSameLanguage = (left, right) => (
  Boolean(comparableLanguageLabel(left)) && comparableLanguageLabel(left) === comparableLanguageLabel(right)
)

const normalizeSearchText = (value) => String(value || '').toLocaleLowerCase().replace(/\s+/g, '')
const normalizeDirectionQuery = (value) => normalizeSearchText(value).replace(
  /翻译成为|翻译成|翻译为|转换成为|转换成|转换为|译成|译为|转成|转为|翻译|转换|->|=>|→|译|转|到|至/g,
  ''
)

const getSearchNames = (language) => {
  return {
    code: language.code || '',
    aliases: language.aliases || [],
    shortcuts: language.shortcuts?.length ? language.shortcuts : [language.label],
  }
}

const shortestShortcut = (values) => [...values].sort((a, b) => a.length - b.length)[0] || ''

const languagePairOptions = computed(() => {
  const generated = languages.value.flatMap((source) => languages.value
    .filter((target) => target.id !== source.id)
    .map((target) => {
      const sourceSearch = getSearchNames(source)
      const targetSearch = getSearchNames(target)
      const value = `${source.label}→${target.label}`
      return {
        label: value,
        value,
        commonRank: COMMON_LANGUAGE_PAIR_RANK.get(`${source.code}→${target.code}`) ?? Number.MAX_SAFE_INTEGER,
        isCustom: source.isCustom || target.isCustom,
        shortLabel: `${shortestShortcut(sourceSearch.shortcuts)}译${shortestShortcut(targetSearch.shortcuts)}`,
        searchText: normalizeSearchText([
          value,
          sourceSearch.code,
          targetSearch.code,
          ...sourceSearch.aliases,
          ...targetSearch.aliases,
        ].join('|')),
        directionSearchText: normalizeSearchText(
          sourceSearch.shortcuts.flatMap((sourceShortcut) => (
            targetSearch.shortcuts.map((targetShortcut) => `${sourceShortcut}${targetShortcut}`)
          )).join('|')
        ),
      }
    }))
  generated.sort((left, right) => left.commonRank - right.commonRank)
  const known = new Set(generated.map((item) => item.value))
  const legacy = parseLanguagePairs(props.modelValue)
    .filter((value) => !known.has(value))
    .map((value) => ({
      label: value,
      value,
      isCustom: true,
      shortLabel: '',
      searchText: normalizeSearchText(value),
      directionSearchText: normalizeDirectionQuery(value),
    }))
  return [...legacy, ...generated]
})

const filteredLanguagePairOptions = computed(() => {
  const tokens = String(searchKeyword.value || '')
    .toLocaleLowerCase()
    .split(/[\s|/]+/)
    .map(normalizeSearchText)
    .filter(Boolean)
  if (!tokens.length) return languagePairOptions.value
  return languagePairOptions.value.filter((item) => tokens.every((token) => {
    const directionToken = normalizeDirectionQuery(token)
    return item.searchText.includes(token)
      || Boolean(directionToken && item.directionSearchText.includes(directionToken))
  }))
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

const filterLanguagePairs = (query) => { searchKeyword.value = query || '' }
const handleVisibleChange = (visible) => {
  if (!visible) searchKeyword.value = ''
}

const hintText = computed(() => loadingFailed.value
  ? '语种候选项加载失败，请刷新页面后重试'
  : '可输入“中英”“中译英”等简称搜索；语种目录由各类项目共享')

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

const findLanguage = (label) => languages.value.find((item) => isSameLanguage(item.label, label))
const addLanguageLocally = (language) => {
  if (!findLanguage(language.label)) languages.value.push(language)
  languages.value.sort((a, b) => Number(a.isCustom) - Number(b.isCustom) || a.label.localeCompare(b.label, 'zh-CN'))
}
const ensureLanguage = async (label) => {
  const existing = findLanguage(label)
  if (existing) return existing
  const created = await createProjectLanguage(label)
  addLanguageLocally(created)
  return created
}
const resetCreateDirection = () => {
  newDirection.value = { source: '', target: '' }
}
const handleCreateCancel = () => {
  createVisible.value = false
  resetCreateDirection()
}
const handleCreateDirection = async () => {
  const sourceLabel = normalizeLanguageLabel(newDirection.value.source)
  const targetLabel = normalizeLanguageLabel(newDirection.value.target)
  if (!sourceLabel || !targetLabel) return ElMessage.warning('请选择或输入原文语种和译文语种')
  if (isSameLanguage(sourceLabel, targetLabel)) return ElMessage.warning('原文语种和译文语种不能相同')
  if (/[→；;,，、\r\n]/.test(sourceLabel) || /[→；;,，、\r\n]/.test(targetLabel)) {
    return ElMessage.warning('语种名称不能包含箭头或列表分隔符')
  }
  creating.value = true
  try {
    const source = await ensureLanguage(sourceLabel)
    const target = await ensureLanguage(targetLabel)
    const pair = `${source.label}→${target.label}`
    selectedPairs.value = [...selectedPairs.value, pair]
    resetCreateDirection()
    createVisible.value = false
    ElMessage.success('翻译方向已添加')
  } catch (error) {
    ElMessage.error(error?.detail || '新增翻译方向失败')
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
.language-pair-shortcut { float: right; margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.new-language-tag { float: right; margin-left: 8px; }
.create-actions { display: flex; justify-content: flex-end; gap: 8px; }
.direction-create-fields { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: end; gap: 10px; }
.direction-create-fields :deep(.el-form-item) { margin-bottom: 16px; }
.direction-create-fields :deep(.el-select) { width: 100%; }
.direction-create-arrow { padding-bottom: 23px; color: var(--el-color-primary); font-size: 20px; font-weight: 700; }

@media (max-width: 600px) {
  .direction-create-fields { grid-template-columns: 1fr; gap: 0; }
  .direction-create-arrow { padding: 0 0 10px; text-align: center; }
}
</style>

<style>
.language-pair-create-popper { max-width: calc(100vw - 24px); }
</style>
