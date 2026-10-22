<template>
  <DraggableFormDialog v-model="visible" title="同时打开多个会话" width="min(640px, calc(100vw - 32px))" top="5vh" append-to-body class="chat-multi-picker" :z-index="100020">
    <div class="chat-multi-picker__mode"><el-radio-group v-model="mode"><el-radio-button value="small">小窗 · 最多 6 个</el-radio-button><el-radio-button value="medium">中窗 · 最多 3 个</el-radio-button></el-radio-group><span>已选 {{ selected.length }}/{{ limit }}</span></div>
    <el-input v-model="keyword" clearable placeholder="搜索会话名称、订单号" aria-label="搜索多窗会话" />
    <p>按屏幕自动分列排列，屏幕较小时可滚动查看。Tab 切换下一窗口输入框，Shift+Tab 切换上一个。</p>
    <el-checkbox-group v-model="selected" class="chat-multi-picker__list">
      <el-checkbox v-for="item in filtered" :key="item.key" :value="item.key" :disabled="!selected.includes(item.key) && selected.length >= limit"><span class="chat-multi-picker__name">{{ item.title }}</span><small>{{ item.subtitle || (item.projectType === 'direct' ? '单聊' : '讨论') }}</small></el-checkbox>
    </el-checkbox-group>
    <el-empty v-if="!filtered.length" description="没有匹配的会话" :image-size="40" />
    <template #footer><el-button @click="selected = []">清空选择</el-button><el-button @click="visible = false">取消</el-button><el-button type="primary" :disabled="!selected.length" @click="apply">打开并平铺 {{ selected.length }} 个窗口</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { matchesSearch } from '@/utils/searchMatching'
import { tileLimit } from '@/utils/chatTiling'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
const props = defineProps({ sessions: {type: Array, default: () => []} })
const { state, openTiledSessions } = useProjectChatDock()
const visible = ref(false), mode = ref('small'), keyword = ref(''), selected = ref([])
const limit = computed(() => tileLimit(mode.value))
const rows = computed(() => [...new Map(props.sessions.map(item => [item.key, item])).values()])
const filtered = computed(() => rows.value.filter(item => matchesSearch(`${item.title || ''} ${item.subtitle || ''}`, keyword.value)))
watch(limit, value => { selected.value = selected.value.slice(0, value) })
function open(value = 'small') {
  mode.value = value === 'medium' ? 'medium' : 'small'; keyword.value = ''
  selected.value = state.windows.filter(item => !item.minimized && rows.value.some(row => row.key === item.key)).map(item => item.key).slice(0, limit.value)
  visible.value = true
}
function apply() {
  const items = selected.value.map(key => rows.value.find(item => item.key === key)).filter(Boolean)
  if (openTiledSessions(items, mode.value)) visible.value = false
}
defineExpose({open})
</script>
<style>
.chat-multi-picker{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.chat-multi-picker>.el-dialog__header,.chat-multi-picker>.el-dialog__footer{flex:none}.chat-multi-picker>.el-dialog__body{min-height:0;overflow-y:auto}.chat-multi-picker>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}
</style>
<style scoped>
.chat-multi-picker__mode{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}.chat-multi-picker p{font-size:12px;color:#64748b}.chat-multi-picker__list{display:flex;flex-direction:column;gap:5px}.chat-multi-picker__list .el-checkbox{height:auto;min-height:48px;margin:0;padding:6px;border-bottom:1px solid #e2e8f0}.chat-multi-picker__list :deep(.el-checkbox__label){white-space:normal;min-width:0}.chat-multi-picker__name{display:block;overflow-wrap:anywhere}.chat-multi-picker__list small{display:block;color:#64748b;margin-top:3px}
</style>
