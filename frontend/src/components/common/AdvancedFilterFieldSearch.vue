<template>
  <div class="advanced-field-search">
    <div v-if="fields.length > 6" class="advanced-field-search__toolbar">
      <el-input v-model="keyword" clearable :prefix-icon="Search" aria-label="搜索高级筛选字段" placeholder="搜索筛选字段名称，支持多个关键词" @keydown.enter.prevent @keydown.stop />
      <div v-if="keyword.trim()" class="advanced-field-search__summary" role="status">匹配 {{ matchedCount }} / {{ fields.length }} 个筛选字段；已设置的条件继续生效</div>
    </div>
    <div ref="contentRef"><slot /></div>
    <div v-if="fields.length > 6 && keyword.trim() && !matchedCount" class="advanced-field-search__empty">没有匹配的筛选字段，请调整或清空关键词</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { matchesSearch } from '@/utils/searchMatching'
import { collectAdvancedFilterFields, applyAdvancedFilterFieldSearch } from '@/utils/advancedFilterFieldSearch'

const props = defineProps({ active: Boolean })
const contentRef = ref(), keyword = ref(''), fields = shallowRef([])
const matchedCount = computed(() => fields.value.filter(field => matchesSearch(field.label, keyword.value)).length)
let observer, queued = false
function apply() {
  applyAdvancedFilterFieldSearch(fields.value, fields.value.length > 6 ? keyword.value : '')
}
function collect() {
  fields.value = collectAdvancedFilterFields(contentRef.value)
  if (fields.value.length <= 6) keyword.value = ''
  apply()
}
function scheduleCollect() {
  if (queued) return
  queued = true
  nextTick(() => { queued = false; if (contentRef.value) collect() })
}
watch(keyword, apply, { flush: 'post' })
watch(() => props.active, async active => {
  if (!active) keyword.value = ''
  await nextTick(); collect()
})
onMounted(() => {
  collect()
  observer = new MutationObserver(scheduleCollect)
  observer.observe(contentRef.value, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['style', 'data-advanced-filter-label'] })
})
onBeforeUnmount(() => { observer?.disconnect(); applyAdvancedFilterFieldSearch(fields.value, '') })
</script>

<style>
.advanced-field-search__toolbar{position:sticky;top:0;z-index:2;padding:0 0 12px;background:var(--el-bg-color-overlay)}
.advanced-field-search__summary{margin-top:6px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.5}
.advanced-field-search__empty{padding:24px 12px;text-align:center;color:var(--el-text-color-secondary);font-size:13px}
.advanced-field-search [data-advanced-filter-search-hidden]{display:none!important}
</style>
