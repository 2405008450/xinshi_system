<template>
  <div class="project-mention-corner" role="region" aria-label="提及消息导航" @mousedown.stop @click.stop>
    <button v-if="collapsed" class="mention-pill" type="button" aria-label="展开提及导航" @click="collapsed = false">@我 {{ count }} 条</button>
    <template v-else>
      <span class="mention-position">{{ model.index >= 0 ? `@我 ${model.index + 1}/${model.total}` : `@我 ${count} 条` }}</span>
      <button type="button" class="mention-arrow" :aria-label="olderLabel" :title="olderLabel"
        :disabled="model.loading || (model.index >= 0 && model.index >= model.total - 1)" @click="older">↑</button>
      <button type="button" class="mention-arrow" aria-label="更新的提及" title="更新的提及"
        :disabled="model.loading || model.index <= 0" @click="activateMove(-1)">↓</button>
      <ProjectMentionPopover :session="session" :model="model" compact @browse="browse" @select="select"
        @more="model.loadMore" @retry="model.refresh" />
      <button type="button" class="mention-close" aria-label="收起提及导航" title="收起提及导航" @click="collapsed = true">×</button>
      <span v-if="model.locating" class="mention-feedback" role="status">正在定位…</span>
      <span v-if="model.notice || model.error" class="mention-feedback" role="alert">{{ model.notice || model.error }} <button type="button" @click="model.refresh">刷新</button></span>
    </template>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import ProjectMentionPopover from './ProjectMentionPopover.vue'
import { useProjectMentionNavigation } from '@/composables/useProjectMentionNavigation'
const props = defineProps({ session: { type: Object, required: true }, selected: Boolean, locate: { type: Function, required: true }, cancelLocate: Function })
const emit = defineEmits(['activate'])
const collapsed = ref(false)
const navigation = useProjectMentionNavigation(item => props.locate(item.messageId), () => props.cancelLocate?.())
const model = navigation.model
const count = computed(() => model.project && !model.loading && !model.error ? model.total : props.session.mentionHistoryCount || 0)
const olderLabel = computed(() => model.index < 0 ? '定位最新提及' : '更早的提及')
function browse() { emit('activate'); navigation.browse(props.session) }
function select(item) { emit('activate'); collapsed.value = false; navigation.browse(props.session); return navigation.select(item) }
function activateMove(direction) { emit('activate'); return navigation.move(direction) }
function older() { emit('activate'); return model.index < 0 ? navigation.latest(props.session) : navigation.move(1) }
watch(() => props.selected, selected => { if (!selected) { navigation.close(); collapsed.value = false } })
defineExpose({ select })
</script>
<style scoped>
.project-mention-corner{display:flex;align-items:center;justify-content:flex-end;gap:4px;flex-wrap:wrap;width:fit-content;max-width:100%;box-sizing:border-box;padding:4px 6px;border:1px solid #dce5f1;border-radius:8px;background:#ffffffef;box-shadow:0 2px 8px #3341550d;color:#5479be;font-size:12px;pointer-events:auto}
.mention-position{white-space:nowrap;padding:0 3px;font-variant-numeric:tabular-nums}
.project-mention-corner button{cursor:pointer;border:0;background:transparent;color:inherit;border-radius:4px}
.mention-arrow,.mention-close{width:26px;height:26px;padding:0;font-size:17px}
.project-mention-corner button:hover:not(:disabled){background:#edf3fc}
.project-mention-corner button:focus-visible{outline:2px solid #5479be}
.project-mention-corner button:disabled{color:#b1bbc9;cursor:default}
.mention-pill{font:inherit;min-height:26px}.mention-feedback{flex-basis:100%;font-size:11px;text-align:right;max-width:240px;overflow-wrap:anywhere}
.mention-feedback[role=alert]{color:#b45309}
</style>
