<template>
  <el-popover trigger="click" placement="left" :width="760" title="语种详情" popper-class="annotation-language-detail-popover" :popper-options="viewportPopperOptions" @show="open">
    <template #reference>
      <el-button link type="primary" class="language-reserve-link" @click.stop>
        {{ items[0]?.display || items[0]?.sourceLanguageLabel || '-' }}
        <span v-if="items.length > 1" class="language-count">+{{ items.length - 1 }}</span>
      </el-button>
    </template>
    <div class="annotation-language-detail-content">
      <div v-if="items.length > 1" class="language-switches" aria-label="切换语种">
        <el-button v-for="(item,index) in items" :key="item.id || index" :type="index === activeIndex ? 'primary' : 'default'" :aria-pressed="index === activeIndex" @click="activeIndex=index">{{ item.display || item.sourceLanguageLabel }}</el-button>
      </div>
      <template v-if="selected">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="语种方向" :span="2">{{ selected.display || selected.sourceLanguageLabel || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地区要求" :span="2">
            <table v-if="selected.regions?.length" class="language-regions-table">
              <thead><tr><th>城市</th><th>区县</th><th>街道</th></tr></thead>
              <tbody><tr v-for="(region,index) in selected.regions" :key="index"><td>{{ region.city || '-' }}</td><td>{{ region.district || '-' }}</td><td>{{ region.street || '-' }}</td></tr></tbody>
            </table>
            <span v-else>未设置地区要求</span>
          </el-descriptions-item>
        </el-descriptions>
        <h4>人才储备</h4>
        <LanguageTalentReserveContent :language-item="selected" :reserves="reserves ?? ownReserves" :loading="reserves === null ? ownLoading : loading" :error="reserves === null ? ownError : error" />
      </template>
    </div>
  </el-popover>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { lookupAnnotationLanguageReserves } from '@/api/annotationProjects'
import LanguageTalentReserveContent from './LanguageTalentReserveContent.vue'

const props = defineProps({
  languageItems: { type: Array, default: () => [] },
  languageItem: { type: Object, default: null },
  reserves: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const items = computed(() => props.languageItems.length ? props.languageItems : props.languageItem ? [props.languageItem] : [])
const activeIndex = ref(0)
const selected = computed(() => items.value[activeIndex.value] || items.value[0])
const ownReserves = ref({}), ownLoading = ref(false), ownError = ref('')
let requestId = 0
const viewportPopperOptions = { modifiers: [{ name: 'preventOverflow', options: { rootBoundary: 'viewport', altAxis: true, tether: false, padding: 16 } }] }
const open = async () => {
  activeIndex.value = 0
  if (props.reserves !== null) return
  const current = ++requestId
  ownReserves.value = {}; ownError.value = ''; ownLoading.value = true
  try {
    const ids = items.value.flatMap(item => [item.sourceLanguageId, item.targetLanguageId]).filter(Boolean)
    const result = ids.length ? await lookupAnnotationLanguageReserves(ids) : { items: [] }
    if (current === requestId) ownReserves.value = Object.fromEntries((result.items || []).map(row => [row.languageId, row]))
  } catch (failure) {
    if (current === requestId) ownError.value = failure.detail || '请稍后重试'
  } finally {
    if (current === requestId) ownLoading.value = false
  }
}
onBeforeUnmount(() => { requestId++ })
</script>

<style scoped>
.language-reserve-link { height:auto; max-width:100%; padding:0; white-space:normal; text-align:left; line-height:1.45; overflow-wrap:anywhere; }
.language-count { margin-left:6px; color:var(--el-text-color-secondary); }
.annotation-language-detail-content { max-height:min(560px, calc(100vh - 120px)); overflow-y:auto; overflow-wrap:anywhere; }
.language-switches { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.language-switches .el-button { height:auto; min-height:32px; margin:0; white-space:normal; }
.language-regions-table { width:100%; border-collapse:collapse; table-layout:fixed; }
.language-regions-table th,.language-regions-table td { padding:6px; border:1px solid var(--el-border-color-lighter); text-align:left; word-break:break-word; }
h4 { margin:16px 0 8px; }
</style>
<style>
.annotation-language-detail-popover { max-width:calc(100vw - 32px)!important; }
.annotation-language-detail-popover .el-descriptions__label { width:100px; min-width:100px; white-space:nowrap; }
.annotation-language-detail-popover .el-descriptions__content { white-space:normal; overflow-wrap:anywhere; }
</style>
