<template>
  <div class="advanced-field-search">
    <div class="advanced-filter-dock-settings"><el-button size="small" link type="primary" @click="configureDock=!configureDock">{{configureDock?'完成设置':'设置常用筛选'}}</el-button><el-button v-if="configureDock" size="small" link @click="dock?.reset()">全部移回</el-button><span v-if="configureDock">点“移出”或拖至查询栏；点“移回”可收回。</span></div>
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
import {createAdvancedFilterDock} from '@/utils/advancedFilterDock'

const props = defineProps({ active: Boolean,anchor:Object,scope:String })
const configureDock=ref(false)
const contentRef = ref(), keyword = ref(''), fields = shallowRef([])
const matchedCount = computed(() => fields.value.filter(field => matchesSearch(field.label, keyword.value)).length)
let observer, queued = false,dock
function apply() {
  applyAdvancedFilterFieldSearch(fields.value.filter(field=>!dock?.isPinned(field)), fields.value.length > 6 ? keyword.value : '')
}
function collect() {
  observer?.disconnect()
  dock ||= createAdvancedFilterDock({root:contentRef.value,anchor:props.anchor,scope:props.scope,onChange:()=>{apply();scheduleCollect()}})
  const collected=collectAdvancedFilterFields(contentRef.value)
  dock?.decorate(collected)
  fields.value = dock?.fields()||collected
  dock?.setEditing(configureDock.value)
  if (fields.value.length <= 6) keyword.value = ''
  apply()
  observer?.observe(contentRef.value,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['style','data-advanced-filter-label']})
}
function scheduleCollect() {
  if (queued) return
  queued = true
  nextTick(() => { queued = false; if (contentRef.value) collect() })
}
watch(keyword, apply, { flush: 'post' })
watch(configureDock,value=>dock?.setEditing(value))
watch(()=>props.anchor,scheduleCollect,{flush:'post'})
watch(() => props.active, async active => {
  if (!active) {keyword.value = '';configureDock.value=false}
  await nextTick(); collect()
})
onMounted(() => {
  collect()
  observer = new MutationObserver(scheduleCollect)
  observer.observe(contentRef.value, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['style', 'data-advanced-filter-label'] })
})
onBeforeUnmount(() => { observer?.disconnect(); applyAdvancedFilterFieldSearch(fields.value, '');dock?.dispose() })
</script>

<style>
.advanced-field-search__toolbar{position:sticky;top:0;z-index:2;padding:0 0 12px;background:var(--el-bg-color-overlay)}
.advanced-field-search__summary{margin-top:6px;color:var(--el-text-color-secondary);font-size:12px;line-height:1.5}
.advanced-field-search__empty{padding:24px 12px;text-align:center;color:var(--el-text-color-secondary);font-size:13px}
.advanced-field-search [data-advanced-filter-search-hidden]{display:none!important}
.advanced-filter-dock-settings{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12px;color:var(--el-text-color-secondary)}
.advanced-filter-dock-toggle{display:none;margin-left:6px;padding:1px 4px;border:1px solid var(--el-border-color);border-radius:3px;background:#fff;color:var(--el-color-primary);font-size:11px;line-height:18px;cursor:grab;white-space:nowrap}
.advanced-filter-drag-ghost{position:fixed;z-index:2147483646;pointer-events:none;padding:6px 12px;background:var(--el-color-primary);color:#fff;border-radius:4px;font-size:13px;box-shadow:0 2px 8px #0002}
.advanced-filter-dock-configuring .advanced-filter-dock-toggle,.advanced-filter-pinned-field .advanced-filter-dock-toggle{display:inline-block}
.advanced-filter-pinned-row{display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap;max-width:100%;min-width:0}.advanced-filter-pinned-row[hidden]{display:none}.advanced-filter-pinned-row>.advanced-filter-pinned-field{flex:0 1 230px;max-width:100%;width:230px;min-width:0;margin:0 0 8px!important;padding:0!important}.advanced-filter-pinned-field .el-form-item{margin:0!important}.advanced-filter-pinned-field .el-input,.advanced-filter-pinned-field .el-select,.advanced-filter-pinned-field .el-date-editor{width:100%!important;min-width:0}.advanced-filter-pinned-field>.el-form-item__label{width:auto!important;float:none!important;height:auto!important;line-height:22px!important}.advanced-filter-pinned-field.el-form-item{display:flex!important;flex-direction:column!important;align-items:stretch}.advanced-filter-pinned-field .el-form-item__content{margin-left:0!important;min-width:0}.advanced-filter-drop-hint{font-size:12px;color:var(--el-color-primary);padding:8px}.advanced-filter-pinned-row.is-configuring,.advanced-filter-pinned-row.is-drop-target{border:1px dashed var(--el-color-primary);border-radius:4px;min-height:36px}
</style>
