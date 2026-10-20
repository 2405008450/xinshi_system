<template>
  <div class="chat-topic-navigation" :class="{ 'is-sidebar': !compact }">
    <el-popover v-if="compact" v-model:visible="menuVisible" trigger="click" placement="bottom-start" :width="300" popper-class="chat-topic-popover">
      <template #reference><el-button text size="small" :aria-label="iconOnly ? '主题' : '讨论主题'" title="讨论主题"><el-icon><Collection /></el-icon><span v-if="!iconOnly">讨论主题</span></el-button></template>
      <TopicMenu />
    </el-popover>
    <TopicMenu v-else />
    <DraggableFormDialog v-if="compact" v-model="resultsVisible" :z-index="100002" :title="`${selected?.path || selected?.name || '讨论主题'} · 消息检索`" width="min(820px, calc(100vw - 32px))" top="5vh" class="issue-dialog chat-topic-results-dialog" append-to-body destroy-on-close>
      <ChatTopicResults :topic="selected" :active="resultsVisible" :all-allowed="allAllowed" :project-id="projectId" :project-type="projectType" @locate="resultsVisible = false" />
      <template #footer><el-button @click="resultsVisible = false">关闭</el-button></template>
    </DraggableFormDialog>
    <ChatTopicManager ref="managerRef" />
  </div>
</template>
<script setup>
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { Collection, Setting, Plus, Search } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { ElButton, ElInput, ElEmpty, ElMessage } from 'element-plus'
import { useChatTopicNavigation } from '@/composables/useChatTopicNavigation'
import { useChatTopics } from '@/composables/useChatTopics'
import { useResourceIssues } from '@/composables/useResourceIssues'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { orderedTopicRoots } from '@/utils/chatTopics'
import ChatTopicManager from './ChatTopicManager.vue'
import ChatTopicResults from './ChatTopicResults.vue'
import '@/views/resource/components/issueDialogs.css'
const props = defineProps({ compact: Boolean, iconOnly: Boolean, allAllowed: Boolean, selectedId: String, projectId: { type: [String, Number], default: '' }, projectType: { type: String, default: '' } })
const emit = defineEmits(['annotation', 'select'])
const route = useRoute(), { topics, refresh } = useChatTopics(), { access, collect, refreshIssueAccess } = useResourceIssues()
const { setLayout } = useProjectChatDock()
const { navigation, toggleRoot, cleanRoots } = useChatTopicNavigation()
const roots = computed(() => orderedTopicRoots(topics.items, route.meta.chatContext))
const menuVisible = ref(false), resultsVisible = ref(false), managerRef = ref(), selected = ref(), filter = ref('')
const activeId = computed(() => props.compact ? selected.value?.id : props.selectedId)
function choose(row) {
  menuVisible.value = false
  if (row.kind === 'annotation') { setLayout('workspace'); emit('annotation'); window.dispatchEvent(new CustomEvent('chat-topic-show-annotation')); return }
  if (!props.projectId && !props.allAllowed) { ElMessage.info('请先选择一个会话'); return }
  selected.value = row
  if (props.compact) resultsVisible.value = true
  else emit('select', row)
}
function openManager() { managerRef.value.open().catch(e => ElMessage.error(e.message)) }
const TopicMenu = defineComponent({ setup: () => () => {
  const term = filter.value.trim().toLocaleLowerCase()
  const matches = row => row.name.toLocaleLowerCase().includes(term)
  const business = roots.value.filter(row => row.kind === 'annotation' && matches(row))
  const discussions = roots.value.filter(row => row.kind !== 'annotation').map(root => {
    const children = topics.items.filter(row => row.parent_id === root.id && row.active)
    return { root, children: !term || matches(root) ? children : children.filter(matches), hasChildren: children.length > 0 }
  }).filter(({ root, children }) => !term || matches(root) || children.length)
  const rowButton = (row, label, child = false) => h('button', { type: 'button', class: ['chat-topic-row', { 'is-active': activeId.value === row.id, 'is-child': child }], 'aria-current': activeId.value === row.id ? 'true' : undefined, title: row.description || row.name, onClick: () => choose(row) }, label || row.name)
  return h('div', { class: 'chat-topic-menu' }, [
    h('div', { class: 'chat-topic-toolbar' }, [
      h(ElInput, { modelValue: filter.value, 'onUpdate:modelValue': value => filter.value = value, clearable: true, placeholder: '搜索主题', 'aria-label': '搜索主题', prefixIcon: Search }),
      topics.can_manage ? h(ElButton, { text: true, icon: Setting, 'aria-label': '管理讨论主题', title: '管理讨论主题', onClick: openManager }) : null,
    ]),
    h('div', { class: 'chat-topic-tree' }, [
      ...(business.length ? [h('div', { class: 'chat-topic-group-label' }, '业务入口'), ...business.map(row => h('div', { key: row.id }, [rowButton(row, [h('span', row.name), h('span', { 'aria-hidden': 'true' }, '›')])]))] : []),
      h('div', { class: 'chat-topic-group-label' }, '讨论主题'),
      ...discussions.map(({ root, children, hasChildren }) => {
        const expanded = !!term || navigation.expanded.includes(root.id)
        if (!hasChildren) return h('div', { key: root.id }, [rowButton(root)])
        return h('div', { key: root.id, class: 'chat-topic-root' }, [
          h('button', { type: 'button', class: 'chat-topic-row', 'aria-expanded': expanded, onClick: () => toggleRoot(root.id) }, [h('span', root.name), h('span', { 'aria-hidden': 'true' }, expanded ? '▾' : '▸')]),
          ...(expanded ? [rowButton(root, '全部消息', true), ...children.map(row => h('div', { key: row.id }, [rowButton(row, '', true)]))] : []),
        ])
      }),
      !business.length && !discussions.length ? h(ElEmpty, { description: term ? '没有匹配的主题' : '暂无讨论主题', imageSize: 40 }) : null,
      topics.error ? h('div', { class: 'chat-topic-error', role: 'alert' }, [topics.error, h(ElButton, { link: true, onClick: () => refresh(true).catch(() => {}) }, () => '重试')]) : null,
    ]),
    access.can_collect ? h('div', { class: 'chat-topic-footer' }, [h(ElButton, { icon: Plus, type: 'primary', plain: true, onClick: () => { menuVisible.value = false; collect('', 'problem') } }, () => '新增开拓事项')]) : null,
  ])
} })
watch(() => [topics.ready, roots.value.map(row => row.id)], ([ready, ids]) => { if (ready) cleanRoots(ids) }, { immediate: true })
onMounted(() => { refresh().catch(() => {}); refreshIssueAccess().catch(() => {}) })
</script>
<style>
.chat-topic-navigation.is-sidebar{height:100%;min-height:0;display:flex;flex-direction:column}
.chat-topic-menu{display:flex;flex-direction:column;min-height:0;max-height:min(520px,calc(100vh - 160px));color:var(--el-text-color-regular)}
.is-sidebar>.chat-topic-menu{flex:1;max-height:none;height:100%}.chat-topic-toolbar{display:flex;gap:4px;align-items:center;padding:8px 4px 16px}.chat-topic-toolbar .el-input{flex:1;min-width:0}.chat-topic-toolbar .el-button{flex:none;margin:0}
.chat-topic-tree{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden}.chat-topic-group-label{padding:12px 10px 8px;font-size:11px;color:var(--el-text-color-secondary);font-weight:600}
.chat-topic-row{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;min-height:40px;border:0;border-radius:6px;background:transparent;padding:9px 12px;font:inherit;font-size:13px;color:inherit;text-align:left;cursor:pointer;overflow-wrap:anywhere}
.chat-topic-row:hover{background:var(--el-fill-color-light)}.chat-topic-row.is-child{padding-left:28px}.chat-topic-row.is-active{background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:600}.chat-topic-row:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:-2px}
.chat-topic-footer{flex:none;border-top:1px solid var(--el-border-color-lighter);padding:14px 4px 6px;margin-top:12px}.chat-topic-footer>.el-button{width:100%;margin:0}.chat-topic-error{font-size:12px;padding:10px;color:var(--el-color-danger)}
.chat-topic-results-dialog .chat-topic-results-panel{height: min(560px, 65vh)}
</style>
