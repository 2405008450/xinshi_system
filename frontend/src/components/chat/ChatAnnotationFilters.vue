<template>
  <span class="chat-annotation-filters" @mousedown.stop @dblclick.stop>
    <el-button size="small" :type="mine ? 'primary' : 'default'" :aria-pressed="mine"
      @click="emit('change', { mine: !mine, statuses })">我是项目经理</el-button>
    <el-popover v-model:visible="visible" trigger="click" placement="bottom-end" :width="320" :z-index="popoverZ"
      popper-class="chat-annotation-status-popover" @show="draft = [...statuses]">
      <template #reference>
        <el-button size="small" :type="statuses.length ? 'primary' : 'default'" :aria-expanded="visible"
          @click="popoverZ = chatOverlayZIndex($event.currentTarget)">项目状态{{ statuses.length ? `（${statuses.length}）` : '' }}</el-button>
      </template>
      <el-checkbox-group v-model="draft" class="chat-annotation-status-options" aria-label="项目状态">
        <el-checkbox v-for="(label, value) in annotationStatusLabels" :key="value" :value="value">{{ label }}</el-checkbox>
      </el-checkbox-group>
      <div class="chat-annotation-status-actions">
        <el-button link @click="apply([])">清空</el-button>
        <el-button size="small" type="primary" @click="apply(draft)">应用</el-button>
      </div>
    </el-popover>
  </span>
</template>

<script setup>
import { ref } from 'vue'
import { annotationStatusLabels } from '@/utils/annotationStatus'
import { chatOverlayZIndex } from '@/utils/chatOverlay'

const props = defineProps({ mine: Boolean, statuses: { type: Array, default: () => [] } })
const emit = defineEmits(['change'])
const visible = ref(false)
const draft = ref([])
const popoverZ = ref(2120)
function apply(statuses) {
  visible.value = false
  emit('change', { mine: props.mine, statuses: [...statuses] })
}
</script>

<style scoped>
.chat-annotation-filters { display:inline-flex; align-items:center; gap:6px; flex:none; }
.chat-annotation-filters .el-button { margin:0; height:21px; padding:0 6px; font-size:11px; }
.chat-annotation-status-options { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); max-height:min(50vh, 320px); overflow:auto; }
.chat-annotation-status-options .el-checkbox { margin:0; }
.chat-annotation-status-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:8px; }
</style>

<style>
.chat-annotation-status-popover { max-width:calc(100vw - 24px); }
</style>
