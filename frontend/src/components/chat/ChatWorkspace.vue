<template>
  <div class="chat-workspace__frame" :class="{ 'chat-workspace--maximized': maximized, 'chat-workspace--narrow': narrow }" :style="{ '--chat-session-width': `${narrow ? 0 : sessionWidth}px` }">
    <header class="chat-workspace__header" :class="{ 'chat-workspace__header--dragging': dragging, 'chat-workspace__header--pinned': maximized }" @mousedown="emit('header-mousedown', $event)" @dblclick="emit('header-dblclick', $event)">
      <el-button v-if="narrow" link aria-label="会话列表" title="会话列表" @click="emit('toggle-sidebar')"><el-icon><ChatDotRound /></el-icon></el-button>
      <div class="chat-workspace__heading" @mousedown.stop @dblclick.stop>
        <strong :title="[title, subtitle].filter(Boolean).join(' · ')">{{ title || '沟通' }}</strong>
        <el-tag v-if="projectType && !narrow" size="small" effect="plain">{{ typeLabel(projectType) }}</el-tag>
        <span v-if="projectType === 'direct' && subtitle && subtitle !== '内部私聊'" class="chat-workspace__subtitle">{{ subtitle }}</span>
      </div>
      <div class="chat-workspace__actions">
        <div id="chat-workspace-session-tools" class="chat-header-session-tools" />
        <ChatTopicNavigation v-if="activeKey" compact icon-only :project-id="projectId" :project-type="projectType" />
        <ChatProjectActions :project-id="projectId" :project-type="projectType" icon-only />
        <el-button v-if="activeKey" link aria-label="聊天记录" title="聊天记录" @click="emit('open-search')"><el-icon><Search /></el-icon></el-button>
        <span class="chat-header-divider" />
        <el-button v-if="activeKey && !narrow" link aria-label="固定小窗" title="固定当前小窗，边聊边工作" @click="emit('pin')"><el-icon><Position /></el-icon></el-button>
        <ChatWindowStateMenu v-if="!narrow" icon-only :size-mode="sizeMode" :maximized="maximized" workspace :has-session="!!activeKey" @resize="emit('resize', $event)" @fullscreen="emit('fullscreen')" @pin="emit('pin')" />
        <el-button link :aria-label="maximized ? '还原窗口' : '最大化'" :title="maximized ? '退出全屏，恢复原窗口' : '全屏沟通'" @click="emit('toggle-maximize')"><span class="chat-max-icon" :class="{ 'chat-max-icon--restore': maximized }" aria-hidden="true" /></el-button>
        <el-button link aria-label="最小化沟通" title="最小化" @click="emit('minimize')"><el-icon><Minus /></el-icon></el-button>
        <el-button link aria-label="关闭聊天大屏" title="关闭大屏，保留会话" @click="emit('minimize')"><el-icon><Close /></el-icon></el-button>
      </div>
    </header>
    <div class="chat-workspace__body">
      <nav v-if="maximized && !narrow" class="chat-workspace__rail" aria-label="沟通导航">
        <span class="chat-workspace__user-avatar" title="我的沟通">{{ chatAvatarText(currentUserName) }}</span>
        <button v-for="item in panes" :key="item.key" type="button" :title="item.label" :aria-label="item.label" :aria-pressed="pane === item.key" :class="{ 'is-active': pane === item.key }" @click="pane = item.key">
          <el-badge :value="unreadTotal" :max="99" :hidden="item.key !== 'messages' || !unreadTotal"><el-icon><component :is="item.icon" /></el-icon></el-badge><small><b v-if="item.key === 'messages' && mentionTotal" class="chat-mention-label">@</b>{{ item.label }}</small>
        </button>
      </nav>
      <aside v-show="!narrow || sidebarOpen" class="chat-workspace__sessions" :style="{ width: `${sessionWidth}px` }">
        <div v-if="!maximized || narrow" class="chat-workspace__pane-tabs" role="tablist" aria-label="沟通导航"><button v-for="item in panes" :key="item.key" type="button" :aria-label="item.label" :aria-pressed="pane === item.key" :class="{ 'is-active': pane === item.key }" @click="pane = item.key"><span>{{ item.label }}</span><b v-if="item.key === 'messages' && mentionTotal" class="chat-mention-label">@</b><span v-if="item.key === 'messages' && unreadTotal" class="chat-pane-count">{{ unreadTotal > 99 ? '99+' : unreadTotal }}</span></button></div>
        <div v-else class="chat-workspace__brand"><strong>{{ pane === 'messages' && (showMentions || annotationMentionView) ? '@我' : panes.find(item => item.key === pane)?.label }}</strong><small>{{ pane === 'messages' ? showMentions ? `${filteredMentionTotal} 条提及` : `${visibleSessions.length} 个会话` : pane === 'contacts' ? '内部通讯录' : '按主题查找消息' }}</small></div>
        <template v-if="pane === 'messages'">
          <div class="chat-workspace__session-tools">
            <div class="chat-workspace__search"><el-input v-model="keyword" clearable size="small" placeholder="搜索名称、订单号、消息" @keyup.enter="applyKeyword"><template #prefix><el-button link :icon="Search" aria-label="查询会话" title="查询" @click="applyKeyword" /></template></el-input></div>
            <div class="chat-workspace__tabs">
              <el-popover v-model:visible="groupsVisible" trigger="click" placement="bottom-end" :width="280" popper-class="chat-session-popover">
                <template #reference><el-button text size="small" class="chat-workspace__filter" :aria-label="`会话分组 ${currentGroupLabel}`" :title="currentGroupLabel"><el-icon><Filter /></el-icon><span class="chat-workspace__filter-label">{{ currentGroupLabel }}</span></el-button></template>
                <div class="chat-session-groups">
                  <el-button v-for="group in groups" :key="group.key" link :type="tab === group.key ? 'primary' : ''" @click="tab = group.key; groupsVisible = false">{{ group.label }} ({{ groupCount(group.key) }})</el-button>
                  <ChatSessionCategoryMenu :sessions="sessions" :selected="tab" @select="tab = $event; groupsVisible = false" @changed="emit('categories-changed')" @editing="groupsVisible = true" />
                </div>
              </el-popover>
            </div>
          </div>
          <div v-if="tab === 'annotation'" class="chat-workspace__annotation-filters">
            <button type="button" class="chat-workspace__status-toggle" :aria-expanded="statusOptionsExpanded" aria-controls="chat-annotation-status-options" :aria-label="statusOptionsExpanded ? '收起状态筛选' : '展开状态筛选'" :title="statusFilterSummary" @click="toggleStatusOptions">
              <span class="chat-workspace__status-caption">状态</span>
              <span class="chat-workspace__status-summary" :class="{ 'has-unread-mention': statusStats(annotationStatus).unread }">{{ annotationStatus ? annotationStatusLabel(annotationStatus) : '不限状态' }} ({{ statusStats(annotationStatus).count }})</span>
              <span v-if="statusStats('').unread" class="chat-status-mention" :title="statusStats(annotationStatus).unread ? '当前状态有未读 @我' : '其他状态有未读 @我'">@我</span>
              <span class="chat-workspace__status-toggle-action">{{ statusOptionsExpanded ? '收起' : '展开' }}<el-icon :class="{ 'is-expanded': statusOptionsExpanded }"><ArrowDown /></el-icon></span>
            </button>
            <div v-show="statusOptionsExpanded" id="chat-annotation-status-options" class="chat-workspace__status-options" role="group" aria-label="标注项目状态">
              <button v-for="status in commonStatusOptions" :key="status.value" type="button" :aria-label="status.label" :title="statusSummary(status.value, status.label)" :aria-pressed="annotationStatus === status.value" :class="{ 'is-active': annotationStatus === status.value, 'has-unread-mention': statusStats(status.value).unread }" @click="annotationStatus = status.value">{{ status.label }} ({{ statusStats(status.value).count }})<span v-if="statusStats(status.value).unread" class="chat-status-mention">@我</span></button>
              <el-popover v-model:visible="moreStatusesVisible" trigger="click" placement="bottom-start" :width="220" :popper-options="statusPopoverOptions" popper-class="chat-session-popover chat-status-popover">
                <template #reference><button type="button" :aria-label="moreStatusLabel" :title="`${moreStatusLabel}：聊天列表中 ${moreStatusStats.count} 个项目${moreStatusStats.unread ? '，有未读 @我' : ''}`" :aria-pressed="isMoreStatus" :class="{ 'is-active': isMoreStatus, 'has-unread-mention': moreStatusStats.unread }">{{ moreStatusLabel }} ({{ moreStatusStats.count }})<span v-if="moreStatusStats.unread" class="chat-status-mention">@我</span><span aria-hidden="true"> ▾</span></button></template>
                <div class="chat-session-groups" role="group" aria-label="更多标注项目状态"><el-button v-for="status in moreStatusOptions" :key="status.value" link :aria-label="status.label" :title="statusSummary(status.value, status.label)" :class="{ 'has-unread-mention': statusStats(status.value).unread }" :type="annotationStatus === status.value ? 'primary' : ''" :aria-pressed="annotationStatus === status.value" @click="selectMoreStatus(status.value)">{{ status.label }} ({{ statusStats(status.value).count }})<span v-if="statusStats(status.value).unread" class="chat-status-mention">@我</span></el-button></div>
              </el-popover>
            </div>
            <div class="chat-workspace__annotation-mode" role="group" aria-label="标注项目消息范围">
              <button type="button" :aria-pressed="!annotationMentions" :class="{ 'is-active': !annotationMentions }" @click="annotationMentions = false">全部会话</button>
              <button type="button" :aria-pressed="annotationMentions" :class="{ 'is-active': annotationMentions }" @click="annotationMentions = true">@我</button>
            </div>
          </div>
          <p v-if="error" class="chat-workspace__error" role="alert">{{ error }} <el-button link @click="emit('retry')">重试</el-button></p>
          <div class="chat-workspace__list">
            <ChatMentionInbox v-if="showMentions" :keyword="appliedKeyword" :active="pane === 'messages'" @total="filteredMentionTotal = $event" @locate="emit('locate-mention', $event)" />
            <template v-else>
            <div class="chat-workspace__result-count">{{ visibleSessions.length }} 个会话</div>
            <el-empty v-if="!visibleSessions.length" :description="annotationMentionView ? '当前筛选中没有提及我的项目' : tab === 'unread' ? '没有未读消息' : '暂无会话'" :image-size="48" />
            <div v-for="session in visibleSessions" :key="session.key" class="chat-workspace__session" :class="{ 'is-active': session.opened && session.key === activeKey, 'is-pinned': session.pinned, 'has-unread-mention': !!session.mentionUnread }" role="button" tabindex="0" :title="[session.title, session.subtitle].filter(Boolean).join(' · ')" @click="emit(session.opened ? 'select' : 'open', session)" @keydown.enter.self="emit(session.opened ? 'select' : 'open', session)" @keydown.space.self.prevent="emit(session.opened ? 'select' : 'open', session)">
              <span class="chat-workspace__avatar" :class="`chat-workspace__avatar--${session.projectType}`" aria-hidden="true">{{ chatAvatarText(session.title) }}<small>{{ typeLabel(session.projectType) }}</small></span>
              <span class="chat-workspace__session-main">
                <span class="chat-workspace__session-title"><strong>{{ session.title || '未命名项目' }}</strong><el-icon v-if="session.starred" title="特别关注" class="chat-session-star"><StarFilled /></el-icon><time :title="formatBusinessDateTime(session.lastMessage?.createdAt)">{{ chatDateLabel(session.lastMessage?.createdAt) }}</time></span>
                <span class="chat-workspace__preview-row"><small class="chat-session-preview"><b v-if="session.mentionUnread" class="chat-mention-label">[有人@我] </b><mark v-else-if="session.lastMessage?.mentionsMe" class="chat-mention-preview">[@我]</mark>{{ session.lastMessage ? `${session.lastMessage.senderName}：${session.lastMessage.preview}` : '暂无消息' }}</small><span v-if="session.unread" class="chat-session-unread">{{ session.unread > 99 ? '99+' : session.unread }}</span></span>
                <ProjectMentionPopover v-if="annotationMentionView" :session="session" :model="projectMentions"
                  @browse="emit('browse-project-mentions', $event)" @select="emit('select-project-mention', $event)"
                  @more="emit('more-project-mentions')" @retry="emit('retry-project-mentions')" />
              </span>
              <el-icon v-if="session.pinned" title="已置顶" class="chat-session-pin"><Top /></el-icon>
              <span class="chat-workspace__session-hover" @click.stop @keydown.stop>
                <el-popover trigger="click" placement="bottom-end" :width="150" popper-class="chat-session-popover"><template #reference><el-button link aria-label="会话操作">⋯</el-button></template><div class="chat-session-groups"><el-button link @click="emit('preference', { session, data: { pinned: !session.pinned } })">{{ session.pinned ? '取消置顶' : '置顶' }}</el-button><el-button link @click="emit('preference', { session, data: { starred: !session.starred } })">{{ session.starred ? '取消特别关注' : '特别关注' }}</el-button><el-button v-if="categories.ready" link @click="categoryAssignment.open(session)">设置分类</el-button><el-button link @click="emit('preference', { session, data: { markRead: true } })">标为已读</el-button></div></el-popover>
                <el-button v-if="session.opened" link class="chat-workspace__session-close" aria-label="关闭会话" title="关闭" @click="emit('close', session)"><el-icon><Close /></el-icon></el-button>
              </span>
            </div>
            </template>
          </div>
        </template>
        <ChatContacts v-show="pane === 'contacts'" :active="pane === 'contacts'" @opened="contactOpened" />
        <div v-show="pane === 'topics'" class="chat-workspace__topic-panel"><ChatTopicNavigation :project-id="projectId" :project-type="projectType" all-allowed @annotation="showAnnotation" /></div>
      </aside>
      <div class="chat-workspace__stage"><div v-if="!activeKey" class="chat-workspace__empty"><el-icon><ChatDotRound /></el-icon><strong>开始沟通</strong><span>选择会话，或从通讯录发起私聊</span></div></div>
      <ChatSessionCategoryAssignment ref="categoryAssignment" @changed="emit('categories-changed', $event)" />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowDown, ChatDotRound, Close, Collection, Filter, Minus, Position, Search, StarFilled, Top, User } from '@element-plus/icons-vue'
import { chatAvatarText, chatDateLabel } from '@/utils/chatLayout'
import { formatBusinessDateTime, businessDateTimeInputValue } from '@/utils/dateTime'
import { annotationStatusLabels, annotationStatusLabel, normalizeAnnotationStatus } from '@/utils/annotationStatus'
import ChatContacts from './ChatContacts.vue'
import ChatMentionInbox from './ChatMentionInbox.vue'
import ProjectMentionPopover from './ProjectMentionPopover.vue'
import ChatProjectActions from './ChatProjectActions.vue'
import ChatWindowStateMenu from './ChatWindowStateMenu.vue'
import ChatTopicNavigation from './ChatTopicNavigation.vue'
import ChatSessionCategoryMenu from './ChatSessionCategoryMenu.vue'
import ChatSessionCategoryAssignment from './ChatSessionCategoryAssignment.vue'
import { categoryKey, useChatSessionCategories } from '@/composables/useChatSessionCategories'

const props = defineProps({
  projectId: { type: String, default: '' },
  sessions: { type: Array, default: () => [] },
  mentionHistoryTotal: { type: Number, default: 0 },
  projectMentions: { type: Object, default: () => ({}) },
  activeKey: { type: String, default: '' },
  error: { type: String, default: '' },
  narrow: { type: Boolean, default: false },
  sidebarOpen: { type: Boolean, default: true },
  sizeMode: { type: String, default: 'medium' },
  maximized: { type: Boolean, default: false },
  sessionWidth: { type: Number, default: 240 },
  title: { type: String, default: '沟通' },
  subtitle: { type: String, default: '' },
  projectType: { type: String, default: '' },
  metaLoading: { type: Boolean, default: false },
  dragging: { type: Boolean, default: false },
})
const emit = defineEmits([
  'browse-project-mentions', 'select-project-mention', 'more-project-mentions', 'retry-project-mentions',
  'preference', 'categories-changed', 'select', 'open', 'locate-mention', 'close', 'close-active', 'minimize', 'cycle-size', 'toggle-maximize', 'toggle-layout',
  'open-search', 'toggle-sidebar', 'header-mousedown', 'header-dblclick', 'retry', 'pin', 'resize', 'fullscreen', 'contact-opened',
])

const panes = [{ key: 'messages', label: '消息', icon: ChatDotRound }, { key: 'contacts', label: '通讯录', icon: User }, { key: 'topics', label: '主题', icon: Collection }]
const paneStorageKey = `xinshi.chatPane.${localStorage.getItem('user_id') || 'anonymous'}`
const currentUserName = localStorage.getItem('user_full_name') || localStorage.getItem('user_name') || '我'
let savedPane = 'messages'
try { savedPane = localStorage.getItem(paneStorageKey) || 'messages' } catch { /* 存储不可用时仍允许切换面板。 */ }
const pane = ref(panes.some(item => item.key === savedPane) ? savedPane : 'messages')
watch(pane, value => { try { localStorage.setItem(paneStorageKey, value) } catch { /* 本次选择仍然生效。 */ } })
const unreadTotal = computed(() => props.sessions.reduce((sum, row) => sum + (Number(row.unread) || 0), 0))
const mentionTotal = computed(() => props.sessions.reduce((sum, row) => sum + (Number(row.mentionUnread) || 0), 0))
const typeLabel = type => type === 'direct' ? '单聊' : type === 'annotation' ? '标注' : '笔译'
function contactOpened() { pane.value = 'messages'; tab.value = 'all'; emit('contact-opened') }
const sessionStamp = value => { const normalized = businessDateTimeInputValue(value); return normalized ? Date.parse(normalized.replace(' ', 'T') + '+08:00') : 0 }
const groups = [{ key: 'all', label: '消息' }, { key: 'pinned', label: '置顶' }, { key: 'unread', label: '未读' }, { key: 'mention', label: '@我' }, { key: 'direct', label: '单聊' }, { key: 'starred', label: '特别关注' }, { key: 'project', label: '项目群' }, { key: 'annotation', label: '标注项目群' }, { key: 'translation', label: '笔译项目群' }, { key: 'creator', label: '我创建的' }]
const { categories } = useChatSessionCategories()
const categoryAssignment = ref()
const currentGroupLabel = computed(() => groups.find(group => group.key === tab.value)?.label || categories.items.find(row => categoryKey(row.id) === tab.value)?.name || '消息')
const storageKey = `xinshi.chatGroup.${localStorage.getItem('user_id') || 'anonymous'}`
let saved = 'all'
try { saved = localStorage.getItem(storageKey) || 'all' } catch { /* 存储不可用时使用默认分组。 */ }
const tab = ref(groups.some(g => g.key === saved) || saved.startsWith('category:') ? saved : 'all')
watch(() => [categories.loaded, categories.ready, categories.items.map(row => `${row.id}:${row.active}`).join(',')], ([loaded, ready]) => {
  if (loaded && tab.value.startsWith('category:') && (!ready || !categories.items.some(row => row.active && categoryKey(row.id) === tab.value))) tab.value = 'all'
})
const groupsVisible = ref(false)
const annotationStatus = ref('')
const annotationMentions = ref(false)
const moreStatusesVisible = ref(false)
const statusOptionsExpanded = ref(true)
function toggleStatusOptions() {
  statusOptionsExpanded.value = !statusOptionsExpanded.value
  moreStatusesVisible.value = false
}
const statusPopoverOptions = { modifiers: [{ name: 'preventOverflow', options: { altAxis: true, tether: false, padding: 16 } }] }
const commonStatuses = ['initial_consultation', 'trial_preparation', 'trial_in_progress', 'project_in_progress', 'client_feedback']
const commonStatusOptions = [{ value: '', label: '不限状态' }, ...commonStatuses.map(value => ({ value, label: annotationStatusLabels[value] }))]
const moreStatusOptions = Object.entries(annotationStatusLabels).filter(([value]) => !commonStatuses.includes(value)).map(([value, label]) => ({ value, label }))
const isMoreStatus = computed(() => !!annotationStatus.value && !commonStatuses.includes(annotationStatus.value))
// 状态入口统计聊天目录中的项目，不受当前状态、关键词或历史提及分页影响。
const annotationStatusStats = computed(() => {
  const stats = { '': { count: 0, unread: false } }
  for (const session of props.sessions) {
    if (session.projectType !== 'annotation') continue
    const status = normalizeAnnotationStatus(session.projectStatus)
    const unread = Number(session.mentionUnread) > 0
    stats[''].count += 1
    stats[''].unread ||= unread
    if (!status) continue
    stats[status] ||= { count: 0, unread: false }
    stats[status].count += 1
    stats[status].unread ||= unread
  }
  return stats
})
const statusStats = status => annotationStatusStats.value[status] || { count: 0, unread: false }
const statusSummary = (status, label) => `${label}：聊天列表中 ${statusStats(status).count} 个项目${statusStats(status).unread ? '，有未读 @我' : ''}`
const statusFilterSummary = computed(() => `${statusSummary(annotationStatus.value, annotationStatus.value ? annotationStatusLabel(annotationStatus.value) : '不限状态')}${!statusStats(annotationStatus.value).unread && statusStats('').unread ? '；其他状态有未读 @我' : ''}`)
const moreStatusLabel = computed(() => isMoreStatus.value ? annotationStatusLabel(annotationStatus.value) : '更多状态')
const moreStatusStats = computed(() => isMoreStatus.value ? statusStats(annotationStatus.value) : moreStatusOptions.reduce((summary, status) => ({
  count: summary.count + statusStats(status.value).count,
  unread: summary.unread || statusStats(status.value).unread,
}), { count: 0, unread: false }))
const showMentions = computed(() => tab.value === 'mention')
const annotationMentionView = computed(() => tab.value === 'annotation' && annotationMentions.value)
const filteredMentionTotal = ref(0)
function selectMoreStatus(value) { annotationStatus.value = value; moreStatusesVisible.value = false }
watch(tab, () => { moreStatusesVisible.value = false; groupsVisible.value = false })
watch(tab, value => { try { localStorage.setItem(storageKey, value) } catch { /* 本次选择仍然生效。 */ } })
function inGroup(session, key) {
  if (key.startsWith('category:')) return !!session.categoryIds?.includes(key.slice('category:'.length))
  if (key === 'all') return true
  if (key === 'creator') return !!session.isCreator
  if (key === 'project') return session.projectType !== 'direct'
  if (['direct', 'annotation', 'translation'].includes(key)) return session.projectType === key
  return !!session[key]
}
const groupCount = key => key === 'mention' ? props.mentionHistoryTotal : props.sessions.filter(s => inGroup(s, key)).length
const keyword = ref('')
const appliedKeyword = ref('')
let keywordTimer = 0

const applyKeyword = () => {
  window.clearTimeout(keywordTimer)
  appliedKeyword.value = keyword.value.trim().toLowerCase()
}

watch(keyword, (value) => {
  window.clearTimeout(keywordTimer)
  if (!value) {
    appliedKeyword.value = ''
    return
  }
  keywordTimer = window.setTimeout(applyKeyword, 400)
})

const visibleSessions = computed(() => props.sessions.filter((session) => {
  if (!inGroup(session, tab.value)) return false
  if (tab.value === 'annotation' && annotationStatus.value && normalizeAnnotationStatus(session.projectStatus) !== annotationStatus.value) return false
  if (annotationMentionView.value && !(Number(session.mentionHistoryCount) > 0)) return false
  if (!appliedKeyword.value) return true
  return `${session.title || ''} ${session.subtitle || ''} ${session.lastMessage?.preview || ''} ${session.lastMessage?.senderName || ''}`.toLowerCase().includes(appliedKeyword.value)
}).sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || Number(!!b.mentionUnread) - Number(!!a.mentionUnread) || sessionStamp(b.lastMessage?.createdAt) - sessionStamp(a.lastMessage?.createdAt)))
function showAnnotation() { pane.value = 'messages'; tab.value = 'annotation' }
onMounted(() => window.addEventListener('chat-topic-show-annotation', showAnnotation))
onBeforeUnmount(() => { window.clearTimeout(keywordTimer); window.removeEventListener('chat-topic-show-annotation', showAnnotation) })
</script>
<style scoped>
.chat-workspace__annotation-filters{flex:none;padding:0 12px 10px;border-bottom:1px solid #e6eaf0}
.chat-session-mention-history{color:#64748b;font-size:11px}
.chat-workspace__status-options{display:flex;flex-wrap:wrap;gap:5px;max-height:min(220px,30vh);overflow-y:auto}
.chat-workspace__annotation-filters button{border:1px solid #dce3ed;border-radius:5px;background:#fff;color:#475569;padding:5px 7px;font:inherit;font-size:12px;cursor:pointer}
.chat-workspace__annotation-filters button.is-active{background:var(--color-primary-soft);border-color:#cbd5e1;color:var(--color-primary-hover)}
.chat-workspace__annotation-filters button.has-unread-mention{color:#b91c1c;border-color:#f2b8b8;background:#fff1f2}
.chat-workspace__annotation-filters button.has-unread-mention.is-active{border-color:#b91c1c;box-shadow:inset 0 0 0 1px #b91c1c}
.chat-status-popover .el-button.has-unread-mention{color:#b91c1c}
.chat-status-popover .el-button[aria-pressed="true"]{background:var(--color-primary-soft);border-radius:5px}
.chat-status-mention{display:inline-block;margin-left:4px;padding:0 3px;border-radius:3px;background:#fee2e2;color:#b91c1c;font-size:10px;line-height:16px}
.chat-workspace__annotation-filters button:focus-visible{outline:2px solid var(--color-primary);outline-offset:1px}
.chat-workspace__annotation-filters .chat-workspace__status-toggle{display:flex;align-items:center;gap:6px;width:100%;min-width:0;margin-bottom:6px;padding:6px 2px;border:0;background:transparent;text-align:left}
.chat-workspace__status-toggle:hover{background:#eef2f8!important}
.chat-workspace__status-caption{flex:none;color:#64748b;font-size:11px}
.chat-workspace__status-summary{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500;color:#334155}
.chat-workspace__status-summary.has-unread-mention{color:#b91c1c}
.chat-workspace__status-toggle-action{display:flex;flex:none;align-items:center;gap:3px;color:#64748b;font-size:11px}
.chat-workspace__status-toggle-action .is-expanded{transform:rotate(180deg)}
.chat-workspace__status-toggle[aria-expanded="false"]{margin-bottom:0}
.chat-workspace__annotation-mode{display:flex;gap:6px;margin-top:10px}
.chat-workspace__annotation-mode button{flex:1}
.chat-workspace__result-count{padding:8px 12px;color:#64748b;font-size:12px}
.chat-workspace__session.has-unread-mention .chat-workspace__session-title strong{color:#b91c1c}
:global(.chat-status-popover){max-width:calc(100vw - 32px);box-sizing:border-box}
:global(.chat-status-popover .chat-session-groups){max-height:min(400px,calc(100vh - 120px))}
.chat-workspace__frame{position:relative;display:flex;width:100%;height:100%;min-height:0;flex-direction:column}
.chat-workspace__header{display:flex;box-sizing:border-box;height:52px;min-height:52px;padding:0 12px;align-items:center;gap:12px;border-bottom:1px solid #e6eaf0;background:white;cursor:grab;user-select:none}
.chat-workspace__header--dragging{cursor:grabbing}.chat-workspace__header--pinned{cursor:default}
.chat-workspace__heading{display:flex;align-items:center;gap:8px;min-width:0;flex:1;cursor:text;user-select:text}.chat-workspace__heading strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px}.chat-workspace__heading .el-tag{flex:none}.chat-workspace__subtitle{font-size:12px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chat-workspace__actions,.chat-header-session-tools{display:flex;align-items:center;gap:2px;flex:none}.chat-workspace__actions :deep(.el-button){margin:0;width:28px;height:28px;padding:4px;flex:none}.chat-header-divider{width:1px;height:20px;background:#e2e8f0;margin:0 6px}
.chat-workspace__body{display:flex;min-height:0;flex:1}.chat-workspace__sessions{display:flex;min-width:0;min-height:0;flex:none;flex-direction:column;overflow:hidden;box-sizing:border-box;border-right:1px solid #e6eaf0;background:#f9fafc}.chat-workspace__brand{display:flex;align-items:center;justify-content:space-between;height:52px;flex:none;padding:0 16px;box-sizing:border-box}.chat-workspace__brand small{font-size:11px;color:#94a3b8}
.chat-workspace__pane-tabs{display:flex;padding:8px;gap:4px;flex:none}.chat-workspace__pane-tabs button{display:flex;flex:1;align-items:center;justify-content:center;gap:4px;min-width:0;border:0;border-radius:6px;padding:7px 2px;font:inherit;font-size:12px;color:#64748b;background:transparent;cursor:pointer;white-space:nowrap}.chat-workspace__pane-tabs .is-active{background:var(--color-primary-soft);color:var(--color-primary-hover);font-weight:600}.chat-pane-count{min-width:16px;padding:0 5px;border-radius:8px;background:#ef4444;color:#fff;font-size:10px;line-height:16px}
.chat-workspace__session-tools{display:flex;align-items:center;gap:4px;padding:8px 10px;flex:none;min-width:0}.chat-workspace__search{flex:1;min-width:0}.chat-workspace__tabs{flex:none;min-width:0}.chat-workspace__tabs .el-button{padding:4px;font-size:12px}.chat-workspace__filter{max-width:108px}.chat-workspace__filter-label{display:inline-block;max-width:64px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}.chat-workspace__list{flex:1;min-height:0;overflow-y:auto;padding:4px 6px 10px}
.chat-workspace__session{position:relative;display:flex;box-sizing:border-box;width:100%;min-height:72px;padding:12px 8px;align-items:center;gap:10px;border-radius:8px;color:#334155;cursor:pointer;font:inherit}.chat-workspace__session.is-pinned{background:#f0f2f5}.chat-workspace__session:hover{background:#edf1f7}.chat-workspace__session.is-active{background:var(--color-primary-soft)}.chat-workspace__session:focus-visible{outline:2px solid var(--color-primary);outline-offset:-2px}
.chat-workspace__avatar{position:relative;display:grid;flex:none;place-items:center;width:38px;height:38px;border-radius:10px;background:#deebff;color:#4979bd;font-size:17px}.chat-workspace__avatar--annotation{background:#dbf1e9;color:#2a8870}.chat-workspace__avatar--direct{border-radius:50%;background:#ece6fa;color:#8268b1}.chat-workspace__avatar small{position:absolute;bottom:-6px;right:-3px;padding:1px 3px;border:2px solid #f9fafc;border-radius:4px;background:#fff;color:#64748b;font-size:8px;line-height:12px}
.chat-workspace__session-main{display:flex;min-width:0;flex:1;flex-direction:column;gap:8px;padding-right:48px}.chat-workspace__session-title,.chat-workspace__preview-row{display:flex;align-items:center;gap:5px;min-width:0}.chat-workspace__session-title strong{font-size:13px;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chat-workspace__session-title time{flex:none;font-size:10px;color:#94a3b8;pointer-events:none}.chat-session-star{color:#d2a235;font-size:12px}.chat-session-preview{display:block;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:#8b96a6}.chat-session-unread{flex:none;min-width:16px;box-sizing:border-box;padding:1px 5px;border-radius:10px;background:#ef6262;color:white;font-size:10px;text-align:center}.chat-mention-label{color:#dc2626}.chat-mention-preview{margin-right:4px;padding:0 3px;border-radius:3px;background:#fef3c7;color:#92400e}.chat-session-pin{position:absolute;top:3px;left:4px;font-size:9px;color:#94a3b8}
.chat-workspace__session-hover{position:absolute;z-index:1;right:8px;top:8px;display:flex;opacity:0;pointer-events:none;border-radius:4px;background:#edf1f7}.chat-workspace__session-hover .el-button{width:22px;height:22px;margin:0}.chat-workspace__session:hover .chat-workspace__session-hover,.chat-workspace__session:focus-within .chat-workspace__session-hover{opacity:1;pointer-events:auto}.chat-workspace__session:hover time,.chat-workspace__session:focus-within time{visibility:hidden;pointer-events:none}
.chat-workspace__stage{min-width:0;flex:1;background:#f6f8fb}.chat-workspace__empty{display:flex;height:100%;align-items:center;justify-content:center;flex-direction:column;gap:14px;color:#94a3b8;font-size:13px}.chat-workspace__empty .el-icon{font-size:44px;color:#c5d2e6}.chat-workspace__empty strong{font-weight:500;font-size:17px;color:#64748b}.chat-workspace__error{padding:8px 12px;color:#b91c1c;font-size:12px}.chat-workspace__topic-panel{flex:1;min-height:0;overflow-y:auto;padding:8px}
.chat-workspace__rail{display:flex;width:56px;box-sizing:border-box;flex:none;flex-direction:column;align-items:center;gap:12px;padding:16px 4px;border-right:1px solid #e6eaf0;background:#eef2f8}.chat-workspace__user-avatar{display:grid;place-items:center;width:32px;height:32px;margin-bottom:14px;border-radius:10px;background:#5479be;color:white;font-size:14px}.chat-workspace__rail button{display:flex;flex-direction:column;align-items:center;gap:6px;width:44px;padding:10px 0;border:0;border-radius:8px;background:transparent;color:#8190a5;cursor:pointer}.chat-workspace__rail button.is-active{background:#e0e9fb;color:#4776c0}.chat-workspace__rail .el-icon{font-size:21px}.chat-workspace__rail small{font-size:10px}.chat-workspace__rail :deep(.el-badge__content){font-size:9px;height:15px;line-height:15px;padding:0 4px}
.chat-workspace--maximized:not(.chat-workspace--narrow){display:grid;grid-template-columns:56px var(--chat-session-width) minmax(0,1fr);grid-template-rows:52px minmax(0,1fr)}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__body{display:contents}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__rail{grid-column:1;grid-row:1 / 3}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__sessions{grid-column:2;grid-row:1 / 3}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__header{grid-column:3;grid-row:1}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__stage{grid-column:3;grid-row:2}
.chat-workspace--narrow .chat-workspace__sessions{position:absolute;z-index:1;top:52px;bottom:0;left:0;max-width:calc(100% - 16px);box-shadow:var(--el-box-shadow-light)}.chat-workspace--narrow .chat-workspace__header{padding:0 6px;gap:4px}.chat-workspace--narrow .chat-workspace__heading strong{font-size:12px}.chat-workspace--narrow .chat-header-divider{margin:0 2px}.chat-workspace--narrow .chat-workspace__subtitle{display:none}.chat-workspace--narrow .chat-workspace__actions{gap:0}
.chat-max-icon{display:inline-block;width:12px;height:12px;box-sizing:border-box;border:1.5px solid currentColor;border-radius:1px}.chat-max-icon--restore{position:relative;border-color:transparent}.chat-max-icon--restore::before,.chat-max-icon--restore::after{content:'';position:absolute;width:8px;height:8px;box-sizing:border-box;border:1.5px solid currentColor;background:white}.chat-max-icon--restore::before{left:0;bottom:0}.chat-max-icon--restore::after{top:0;right:0}
.chat-session-groups{display:flex;flex-direction:column;align-items:stretch;max-height:400px;overflow:auto}.chat-session-groups .el-button{margin:0;justify-content:flex-start;padding:8px}
</style>
