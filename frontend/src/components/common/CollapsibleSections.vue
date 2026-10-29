<template>
  <div ref="root" class="collapsible-sections">
    <div class="section-expansion-toolbar" role="group" aria-label="区域展开设置">
      <el-button size="small" @click="setAll(true)">全部展开</el-button>
      <el-button size="small" @click="setAll(false)">全部折叠</el-button>
      <el-button size="small" title="展开当前收起区域的一半" @click="setHalf(true)">展开一半</el-button>
      <el-button size="small" title="收起当前展开区域的一半" @click="setHalf(false)">折叠一半</el-button>
      <div v-if="$slots.actions" class="section-expansion-actions"><slot name="actions" /></div>
    </div>
    <el-collapse v-model="expanded"><slot /></el-collapse>
  </div>
</template>
<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = defineProps({ resetKey: { type: [String, Number], default: '' } })
const root = ref(null), expanded = ref([])
let observer
const keys = () => [...(root.value?.querySelectorAll('[data-section-key]') || [])].map(node => node.dataset.sectionKey)
function reset() { expanded.value = keys().slice(0, 1) }
function setAll(open) { expanded.value = open ? keys() : [] }
function setHalf(open) {
  const candidates = keys().filter(key => open ? !expanded.value.includes(key) : expanded.value.includes(key))
  const targets = candidates.slice(0, Math.ceil(candidates.length / 2))
  expanded.value = open ? [...expanded.value, ...targets] : expanded.value.filter(key => !targets.includes(key))
}
onMounted(() => {
  reset()
  observer = new MutationObserver(() => {
    const available = new Set(keys())
    const next = expanded.value.filter(key => available.has(key))
    if (next.length !== expanded.value.length) expanded.value = next
  })
  observer.observe(root.value, { childList: true, subtree: true })
})
watch(() => props.resetKey, async () => { await nextTick(); reset() })
onBeforeUnmount(() => observer?.disconnect())
defineExpose({ reset, setAll, setHalf })
</script>
<style scoped>
.section-expansion-toolbar{position:sticky;top:0;z-index:4;display:flex;gap:6px;flex-wrap:wrap;padding:10px 0;background:var(--el-bg-color)}
.section-expansion-toolbar .el-button+.el-button{margin-left:0}
.section-expansion-actions{margin-left:auto;display:flex;align-items:center;gap:8px;max-width:100%;min-width:0}
.collapsible-sections :deep(.el-collapse-item__header){height:auto;min-height:44px;line-height:1.5;padding:10px 12px;font-size:15px;font-weight:600}
.collapsible-sections :deep(.el-collapse-item__content){padding-bottom:12px}
</style>
