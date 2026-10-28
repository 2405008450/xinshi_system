<template>
  <div class="chat-workspace__frame" :class="{ 'chat-workspace--maximized': maximized, 'chat-workspace--wide-header': wideHeader, 'chat-workspace--narrow': narrow, 'chat-workspace--mobile': mobile, 'chat-workspace--list': listView, 'chat-workspace--chat': chatView, 'chat-workspace--compact-header': pane === 'summary','chat-workspace--summary':['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane) }" :style="{ '--chat-session-width': `${narrow ? 0 : sessionWidth}px` }">
    <header class="chat-workspace__header" :class="{ 'chat-workspace__header--dragging': dragging, 'chat-workspace__header--pinned': maximized }" @mousedown="emit('header-mousedown', $event)" @dblclick="emit('header-dblclick', $event)">
      <el-button v-if="narrow && !listView" link :aria-label="mobile ? '返回会话列表' : '会话列表'" :title="messageBadgeTotal ? `${messageBadgeTotal} 条未读 @我，点击查看会话列表` : (mobile ? '返回会话列表' : '会话列表')" @click="openMobileSessions"><el-badge :value="messageBadgeTotal" :max="99" :hidden="!messageBadgeTotal"><el-icon><ArrowLeft v-if="mobile" /><ChatDotRound v-else /></el-icon></el-badge></el-button>
      <div class="chat-workspace__heading" @mousedown.stop @dblclick.stop>
        <ChatOrderIdentity v-if="!listView && !['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane) && ['annotation', 'translation'].includes(projectType) && subtitle" :title="title" :order-no="subtitle" :project-type="projectType" :project-id="projectId" show-managers />
        <strong v-else :title="title">{{ listView ? mobileListTitle : pane==='summary'?'总结':pane==='notifications'?'通知':isProjectPane(pane)?`${projectMine ? '我的' : ''}${panes.find(item=>item.key===pane)?.label || ''}`:title || '沟通' }}</strong>
        <el-tag v-if="projectType && !narrow" size="small" effect="plain">{{ typeLabel(projectType) }}</el-tag>
        <span v-if="projectType === 'direct' && subtitle && subtitle !== '内部私聊'" class="chat-workspace__subtitle">{{ subtitle }}</span>
      </div>
      <div v-show="pane !== 'summary' && !listView" class="chat-header-command-row" title="横向滚动查看更多操作" @mousedown.stop>

      <div class="chat-workspace__actions">
        <ChatConversationMore :project-id="projectId" :project-type="projectType" :can-duplicate="['annotation','translation'].includes(projectType) && !!activeKey" @duplicate="emit('duplicate-window')" @multiple="emit('open-multiple')">
          <div id="chat-workspace-session-tools" class="chat-header-session-tools" />
        <ChatConversationParticipants menu-layout v-if="['translation', 'discussion'].includes(projectType) && projectId" :key="`${projectType}:${projectId}`" :project-id="projectId" :project-type="projectType" />
          <AnnotationChatInbox menu-layout @conversation-opened="pane='messages'" @navigate="emit('project-navigate')" />
        </ChatConversationMore>
        <span class="chat-header-divider" />
        <el-button v-if="activeKey && !narrow" link aria-label="固定小窗" title="固定当前小窗，边聊边工作" @click="emit('pin')"><el-icon><ChatPinIcon /></el-icon></el-button>
      </div>
      </div>
      <div class="chat-fixed-window-controls" @mousedown.stop @dblclick.stop><ChatProjectEntry v-if="pane !== 'summary' && !listView" :project-id="projectId" :project-type="projectType" @navigate="emit('project-navigate')" /><el-button v-if="pane !== 'summary' && activeKey && !listView" link aria-label="聊天记录" title="聊天记录" @click="emit('open-search')"><el-icon><Search /></el-icon></el-button><button type="button" aria-label="最小化会话窗口" title="最小化" @click="emit('minimize')">−</button><button v-if="!maximized" type="button" aria-label="最大化会话窗口" title="最大化" @click="emit('toggle-maximize')">□</button><button v-else type="button" aria-label="还原会话窗口" title="还原窗口（正常大小）" @click="emit('normal-size')">▣</button><button type="button" aria-label="退出整个会话窗口" title="退出整个会话窗口，保留聊天记录" @click.stop="emit('exit-workspace')">×</button></div>
    </header>
    <div class="chat-workspace__body">
      <nav v-if="maximized && !narrow" class="chat-workspace__rail" aria-label="沟通导航">
        <span class="chat-workspace__user-avatar" title="我的沟通">{{ chatAvatarText(currentUserName) }}</span>
        <button v-for="item in panes" :key="item.key" type="button" :title="item.key === 'messages' && mentionTotal ? `${mentionTotal} 条未读 @我，点击查看` : item.label" :aria-label="item.label" :aria-pressed="pane === item.key" :class="{ 'is-active': pane === item.key }" @click="selectPane(item.key)" @contextmenu="openProjectMenu($event,item.key)" @keydown.shift.f10="openProjectMenu($event,item.key)">
          <el-badge :value="item.key === 'notifications' ? notificationBadgeTotal : messageBadgeTotal" :max="99" :hidden="item.key === 'notifications' ? !notificationBadgeTotal : item.key !== 'messages' || !messageBadgeTotal" @click.stop="badgeClick(item.key)"><el-icon><component :is="item.icon" /></el-icon></el-badge><small><b v-if="item.key === 'messages' && mentionTotal" class="chat-mention-label">@</b>{{ item.label }}</small>
        </button>
      </nav>
      <aside v-show="!['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane) && (!narrow || sidebarOpen)" class="chat-workspace__sessions" :style="{ width: `${sessionWidth}px` }">
        <div v-if="!maximized || narrow" class="chat-workspace__pane-tabs" role="tablist" aria-label="沟通导航"><button v-for="item in panes" :key="item.key" type="button" :aria-label="item.label" :aria-pressed="pane === item.key" :class="{ 'is-active': pane === item.key }" @click="selectPane(item.key)" @contextmenu="openProjectMenu($event,item.key)" @keydown.shift.f10="openProjectMenu($event,item.key)"><span>{{ item.label }}</span><b v-if="item.key === 'messages' && mentionTotal" class="chat-mention-label">@</b><span v-if="item.key === 'notifications' && notificationBadgeTotal" class="chat-pane-count" @click.stop="badgeClick(item.key)">{{ notificationBadgeTotal > 99 ? '99+' : notificationBadgeTotal }}</span><span v-if="item.key === 'messages' && messageBadgeTotal" class="chat-pane-count">{{ messageBadgeTotal > 99 ? '99+' : messageBadgeTotal }}</span></button></div>
        <div v-else class="chat-workspace__brand"><strong>{{ pane === 'messages' && (showMentions || annotationMentionView) ? '@我' : panes.find(item => item.key === pane)?.label }}</strong><small>{{ pane === 'messages' ? showMentions ? `${filteredMentionTotal} 条提及` : '' : pane === 'contacts' ? '内部通讯录' : '' }}</small></div>
        <template v-if="pane === 'messages'">
          <div class="chat-workspace__session-tools">
            <div class="chat-workspace__search"><el-select v-model="searchMode" size="small" class="chat-search-mode" popper-class="chat-search-mode-options" aria-label="搜索范围"><el-option label="会话" value="sessions" /><el-option label="聊天记录" value="messages" /></el-select><el-input v-model="keyword" clearable size="small" :placeholder="searchPlaceholder" @keyup.enter="applyKeyword"><template #prefix><el-button link :icon="Search" aria-label="查询会话" title="查询" @click="applyKeyword" /></template></el-input></div>
            <div class="chat-workspace__tabs">
              <el-popover v-model:visible="groupsVisible" trigger="click" placement="bottom-end" :width="280" popper-class="chat-session-popover">
                <template #reference><el-button text size="small" class="chat-workspace__filter" :aria-label="`会话分组 ${currentGroupLabel}`" :title="currentGroupLabel"><el-icon><Filter /></el-icon><span class="chat-workspace__filter-label">{{ currentGroupLabel }}</span></el-button></template>
                <div class="chat-session-groups">
                  <el-button v-for="group in groups" :key="group.key" link :type="tab === group.key ? 'primary' : ''" @click="tab = group.key; groupsVisible = false">{{ group.label }} ({{ groupCount(group.key) }})</el-button>
                </div>
              </el-popover>
            </div>
          </div>
          <div class="chat-workspace__annotation-filters">
            <div class="chat-workspace__annotation-mode" role="group" aria-label="消息范围">
              <button type="button" :aria-pressed="annotationMode === 'group'" :class="{ 'is-active': annotationMode === 'group' }" @click="annotationMode = 'group'">群聊</button>
              <button type="button" :aria-pressed="annotationMode === 'direct'" :class="{ 'is-active': annotationMode === 'direct' }" @click="annotationMode = 'direct'">单聊</button>
              <button type="button" :aria-pressed="annotationMode === 'mention'" :class="{ 'is-active': annotationMode === 'mention' }" @click="annotationMode = 'mention'" @contextmenu="mentionSortMenu?.open($event)" @keydown.shift.f10="mentionSortMenu?.open($event)">@我</button>
            </div>
          </div>
          <ChatSessionFolderTree ref="folderTreeRef" v-if="annotationMode !== 'direct'" :compact="mobile" :selected="selectedFolder" :active="active" :sessions="allMentionSessions" @select="selectFolder" @unread="openFolderUnread" @changed="emit('categories-changed')" @browse-annotation="annotationPickerVisible = true" @open-conversation="emit('open', $event)" />
          <div class="chat-workspace__recent-closed">
            <el-popover v-model:visible="recentClosedVisible" :z-index="recentMenuZ" trigger="click" placement="right-start" :width="300">
              <template #reference><el-button text size="small" @click="prepareRecentMenu">最近关闭（{{ recentInFolder.length }}/10）</el-button></template>
              <div class="chat-recent-closed" aria-label="最近关闭的会话">
                <div class="chat-recent-closed__tools"><span>最新关闭的会话</span><el-button link type="primary" :disabled="!recentClosed.length" @click="restoreAllRecent">一键恢复全部（{{ Math.min(recentClosed.length, 10) }}）</el-button></div>
                <p v-if="!recentInFolder.length">当前分组暂无关闭记录</p>
                <div v-for="item in recentInFolder" :key="item.key" class="chat-recent-closed__item">
                  <span :title="item.title"><strong>{{ item.title }}</strong><small>{{ item.subtitle || typeLabel(item.projectType) }}</small></span>
                  <el-button link type="primary" :aria-label="`恢复 ${item.title}`" @click="restoreRecent(item)">恢复</el-button>
                </div>
              </div>
            </el-popover>
          </div>
          <p v-if="error" class="chat-workspace__error" role="alert">{{ error }} <el-button link @click="emit('retry')">重试</el-button></p>
          <div ref="sessionList" class="chat-workspace__list" @contextmenu="annotationMentionView && mentionSortMenu?.open($event)" @keydown.shift.f10="annotationMentionView && mentionSortMenu?.open($event)">
            <ChatMessageSearchResults v-if="searchMode === 'messages'" :keyword="appliedKeyword" :revision="searchRevision" @locate="emit('locate-mention', $event)" /><ChatMentionInbox v-else-if="showMentions" :keyword="appliedKeyword" :filters="mentionFilters" :active="pane === 'messages'" @total="filteredMentionTotal = $event" @locate="emit('locate-mention', $event)" />
            <template v-else>
            <el-empty v-if="!visibleSessions.length" :description="annotationMentionView ? '当前筛选中没有提及我的项目' : tab === 'unread' ? '没有未读消息' : '暂无会话'" :image-size="48" />
            <div v-for="session in visibleSessions" :key="session.key" class="chat-workspace__session" :class="{ 'is-active': session.opened && session.key === activeKey, 'is-pinned': session.pinned, 'has-unread-mention': !!session.mentionUnread }" role="button" tabindex="0" :title="[session.title, session.subtitle].filter(Boolean).join(' · ')" @click="emit(session.opened ? 'select' : 'open', session)" @keydown.enter.self="emit(session.opened ? 'select' : 'open', session)" @keydown.space.self.prevent="emit(session.opened ? 'select' : 'open', session)">
              <span class="chat-workspace__session-left"><span v-if="session.projectType !== 'direct' && Number.isFinite(session.memberCount)" class="chat-session-member-count" :title="`当前会话 ${session.memberCount} 位参与人`" :aria-label="`当前会话 ${session.memberCount} 人`">{{ session.memberCount }}人</span><span class="chat-workspace__avatar" :class="`chat-workspace__avatar--${session.projectType}`" aria-hidden="true">{{ chatAvatarText(session.title) }}<small>{{ typeLabel(session.projectType) }}</small></span></span>
              <span class="chat-workspace__session-main">
                <span class="chat-workspace__session-title"><strong>{{ session.title || '未命名项目' }}</strong><el-icon v-if="session.starred" title="特别关注" class="chat-session-star"><StarFilled /></el-icon><time v-if="sessionDisplayTime(session)" :title="formatBusinessDateTime(sessionDisplayTime(session))">{{ chatDateLabel(sessionDisplayTime(session)) }}</time></span>
                <ChatOrderIdentity :order-no="session.subtitle" :project-type="session.projectType" />
                <span v-if="renamingDiscussion?.key === session.key" @click.stop @keydown.stop @mousedown.stop><ChatInlineNameEditor :initial-name="session.title" class="chat-compact-rename" label="会话名称" :saving="renameSaving" :error="renameError" @save="saveDiscussionName" @cancel="renamingDiscussion = null" /></span>
                <span class="chat-workspace__preview-row"><small class="chat-session-preview"><b v-if="session.mentionUnread" class="chat-mention-label">[有人@我] </b><mark v-else-if="session.lastMessage?.mentionsMe" class="chat-mention-preview">[@我]</mark>{{ session.lastMessage ? `${session.lastMessage.senderName}：${screenshotPreview(session.lastMessage.preview)}` : session.projectType === 'discussion' && session.storageReady !== true ? '讨论暂未启用' : '暂无消息' }}</small><span v-if="session.mentionUnread" class="chat-session-unread" :aria-label="`${session.mentionUnread} 条未读提及`" title="未读 @我">{{ session.mentionUnread > 99 ? '99+' : session.mentionUnread }}</span><span v-if="sessionUnreadSignal(session).ordinary" class="chat-session-unread-dot" role="status" aria-label="有普通未读消息" title="有普通未读消息" /></span>
                <span v-if="session.variants.length > 1" class="chat-session-orders" @click.stop @keydown.stop>
                  <el-popover trigger="click" placement="right-start" :width="280">
                    <template #reference><el-button link size="small" :aria-label="`切换订单会话 ${session.subtitle}`">切换订单</el-button></template>
                    <div class="chat-session-order-options">
                      <el-button v-for="variant in session.variants" :key="variant.key" link :type="variant.key === activeKey ? 'primary' : ''" @click="emit(variant.opened ? 'select' : 'open', variant)">{{ variant.subtitle }}<span v-if="variant.mentionUnread">（{{ variant.mentionUnread }} 条未读 @我）</span></el-button>
                    </div>
                  </el-popover>
                </span>
                <ProjectMentionPopover v-if="annotationMentionView && session.projectType === 'annotation'" :session="session" :model="projectMentions"
                  @browse="emit('browse-project-mentions', $event)" @select="emit('select-project-mention', $event)"
                  @more="emit('more-project-mentions')" @retry="emit('retry-project-mentions')" />
              </span>
              <el-icon v-if="session.pinned" title="已置顶" class="chat-session-pin"><Top /></el-icon>
              <span class="chat-workspace__session-controls" @click.stop @keydown.stop @mousedown.stop>
                <template v-if="session.projectType === 'discussion'"><el-button v-if="categories.canManage && !session.technicalProjectId" link class="chat-rename-button" :aria-label="`修改名称 ${session.title}`" @click="startDiscussionRename(session)">修改名称</el-button><el-button v-if="categories.canManage && session.subtitle !== '资源开拓讨论'" link class="chat-rename-button" type="danger" @click="deleteDiscussion(session)">删除会话</el-button><small v-if="!categories.canManage" class="chat-discussion-protected">固定讨论</small></template>
                <template v-else>
                  <el-popover trigger="click" placement="bottom-end" :width="150" popper-class="chat-session-popover"><template #reference><el-button link aria-label="会话操作">⋯</el-button></template><div class="chat-session-groups"><el-button link @click="emit('preference', { session, data: { pinned: !session.pinned } })">{{ session.pinned ? '取消置顶' : '置顶' }}</el-button><el-button link @click="emit('preference', { session, data: { starred: !session.starred } })">{{ session.starred ? '取消特别关注' : '特别关注' }}</el-button><el-button v-if="categories.ready" link @click="categoryAssignment.open(session)">设置分类</el-button><el-button link @click="emit('preference', { session, data: { markRead: true } })">标为已读</el-button></div></el-popover>
                </template>
              </span>
            </div>
            </template>
          </div>
        </template>
        <ChatContacts v-show="pane === 'contacts'" :active="pane === 'contacts'" @opened="contactOpened" />
        <ChatSettings v-if="pane === 'settings'" />
      </aside>
      <div class="chat-workspace__stage"><template v-if="['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane)"><div v-if="!maximized||narrow" class="chat-workspace__pane-tabs" role="tablist" aria-label="沟通导航"><button v-for="item in panes" :key="item.key" :aria-label="item.label" @click="selectPane(item.key)" @contextmenu="openProjectMenu($event,item.key)" @keydown.shift.f10="openProjectMenu($event,item.key)">{{ item.label }}<span v-if="item.key === 'messages' && messageBadgeTotal" class="chat-pane-count">@{{ messageBadgeTotal > 99 ? '99+' : messageBadgeTotal }}</span></button></div><div class="chat-summary-content"><ChatRequestNotifications v-if="pane==='notifications'" :feed="notificationFeed" /><ChatAnnotationProjects v-else-if="pane==='annotation-projects'" :key="`annotation:${projectMine}`" :my-projects="projectMine" @navigate="emit('project-navigate')" @open-conversation="pane='messages'" /><ChatManagedProjects v-else-if="isProjectPane(pane)" :key="`${pane}:${projectMine}`" :module="projectModule(pane)" :my-projects="projectMine" /><DevelopmentIssuePanel v-else :open-issue-id="summaryIssueId" /></div></template><div v-else-if="!activeKey" class="chat-workspace__empty"><el-icon><ChatDotRound /></el-icon><strong>开始沟通</strong><span>选择会话，或从通讯录发起私聊</span></div></div>
      <el-popover v-model:visible="projectMenuVisible" :virtual-ref="projectMenuAnchor" virtual-triggering :trigger="[]" placement="right-start" :width="150" :z-index="100050"><el-button text @click="selectMyProjects">我的项目</el-button></el-popover>
      <ChatMentionSortMenu ref="mentionSortMenu" v-model="mentionSort" />
      <ChatSessionCategoryAssignment ref="categoryAssignment" @changed="emit('categories-changed', $event)" />
      <ChatAnnotationProjectPicker v-model="annotationPickerVisible" @joined="joinedAnnotation" />
    </div>
    <nav v-if="mobile && !chatView" class="chat-mobile-tabbar" aria-label="沟通导航">
      <button v-for="item in mobileTabs" :key="item.key" type="button" :class="{ 'is-active': pane === item.key }" :aria-pressed="pane === item.key" @click="mobileSelectPane(item.key)">
        <el-badge :value="item.badge" :max="99" :hidden="!item.badge"><el-icon><component :is="item.icon" /></el-icon></el-badge><span>{{ item.label }}</span>
      </button>
      <el-popover v-for="group in mobileGroups" :key="group.label" v-model:visible="mobileGroupVisible[group.label]" trigger="click" placement="top" :width="170" popper-class="chat-mobile-group-popover">
        <template #reference>
          <button type="button" :class="{ 'is-active': group.items.some(item => item.key === pane) }"><el-icon><component :is="group.icon" /></el-icon><span>{{ group.label }}</span></button>
        </template>
        <div class="chat-mobile-group"><button v-for="item in group.items" :key="item.key" type="button" :class="{ 'is-active': pane === item.key }" @click="mobileGroupVisible[group.label] = false; mobileSelectPane(item.key)">{{ item.label }}</button></div>
      </el-popover>
    </nav>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { screenshotPreview } from '@/utils/screenshotReferences'
import {activeConversationFolder} from '@/utils/chatActiveFolder'
import { matchesSearch } from '@/utils/searchMatching'
import ChatOrderIdentity from './ChatOrderIdentity.vue'
import { chatRequest } from '@/api/projectChat'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import ChatMentionSortMenu from './ChatMentionSortMenu.vue'
import { compareMentionSessions, latestMentionAt } from '@/utils/chatMentionSort'
import { groupSessionList, sessionListKey, mentionUnreadCount, sessionUnreadSignal, firstUnreadMentionSession, compareSessionActivity } from '@/utils/chatSessionList'

import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Bell, ArrowLeft, ChatDotRound, Collection, Headset, Filter, MoreFilled, Search, Setting, StarFilled, Top, User, EditPen, Microphone, Phone } from '@element-plus/icons-vue'
const DevelopmentIssuePanel=defineAsyncComponent(()=>import('@/views/resource/components/DevelopmentIssuePanel.vue'))
import ChatSettings from './ChatSettings.vue'
import { hasPermission } from '@/utils/permission'
import AnnotationChatInbox from './AnnotationChatInbox.vue'
const ChatAnnotationProjects = defineAsyncComponent(() => import('./ChatAnnotationProjects.vue'))
const ChatManagedProjects = defineAsyncComponent(() => import('./ChatManagedProjects.vue'))
import ChatProjectEntry from './ChatProjectEntry.vue'
import ChatRequestNotifications from './ChatRequestNotifications.vue'
import { useChatRequestNotifications } from '@/composables/useChatRequestNotifications'
const notificationFeed = useChatRequestNotifications()
import ChatConversationParticipants from './ChatConversationParticipants.vue'
import { chatAvatarText, chatDateLabel } from '@/utils/chatLayout'
import { formatBusinessDateTime } from '@/utils/dateTime'
import ChatContacts from './ChatContacts.vue'
import ChatMentionInbox from './ChatMentionInbox.vue'
import ChatMessageSearchResults from './ChatMessageSearchResults.vue'
import ProjectMentionPopover from './ProjectMentionPopover.vue'
import ChatConversationMore from './ChatConversationMore.vue'
import ChatPinIcon from './ChatPinIcon.vue'
import ChatSessionFolderTree from './ChatSessionFolderTree.vue'
import ChatAnnotationProjectPicker from './ChatAnnotationProjectPicker.vue'
import { normalizeAnnotationStatus } from '@/utils/annotationStatus'
import { annotationFolderId, resourceFolderId, resourceDiscussionIds, sessionFolderNodes, sessionMatchesFolder } from '@/utils/chatSessionFolders'
import ChatSessionCategoryAssignment from './ChatSessionCategoryAssignment.vue'
import { categoryKey, useChatSessionCategories } from '@/composables/useChatSessionCategories'

const props = defineProps({
  wideHeader: Boolean,
  active: { type: Boolean, default: true },
  projectId: { type: String, default: '' },
  sessions: { type: Array, default: () => [] },
  searchSessions: { type: Array, default: () => [] },
  recentClosed: { type: Array, default: () => [] },
  mentionHistoryTotal: { type: Number, default: 0 },
  messageNotificationTotal: { type: Number, default: null },
  projectMentions: { type: Object, default: () => ({}) },
  activeKey: { type: String, default: '' },
  error: { type: String, default: '' },
  narrow: { type: Boolean, default: false },
  mobile: { type: Boolean, default: false },
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
  'restore-closed', 'browse-project-mentions', 'select-project-mention', 'more-project-mentions', 'retry-project-mentions',
  'project-navigate', 'normal-size', 'context-empty', 'duplicate-window', 'open-multiple', 'pane-change', 'preference', 'categories-changed', 'select', 'open', 'locate-mention', 'close', 'close-active', 'exit-workspace', 'minimize', 'cycle-size', 'toggle-maximize', 'toggle-layout',
  'open-search', 'toggle-sidebar', 'header-mousedown', 'header-dblclick', 'retry', 'pin', 'resize', 'fullscreen', 'contact-opened',
])

const panes = [{ key: 'messages', label: '消息', icon: ChatDotRound }, { key: 'contacts', label: '通讯录', icon: User }, { key: 'summary', label: '总结', icon: Collection }, { key: 'notifications', label: '通知', icon: Bell }, ...(hasPermission('projects:read') ? [{ key: 'annotation-projects', label: '标注项目', icon: Headset },{key:'translation-projects',label:'笔译项目',icon:EditPen},{key:'interpretation-projects',label:'口译项目',icon:Microphone}] : []), ...(hasPermission('consultations:read')?[{key:'consultations',label:'新咨询管理',icon:Phone}]:[]), { key: 'settings', label: '设置', icon: Setting }]
const paneStorageKey = `xinshi.chatPane.${localStorage.getItem('user_id') || 'anonymous'}`
const currentUserName = localStorage.getItem('user_full_name') || localStorage.getItem('user_name') || '我'
let savedPane = 'messages'
try { savedPane = localStorage.getItem(paneStorageKey) || 'messages' } catch { /* 存储不可用时仍允许切换面板。 */ }
const pane = ref(panes.some(item => item.key === savedPane) ? savedPane : 'messages')
const sessionList = ref(null)
const summaryIssueId=ref('')
watch(pane, value => { try { localStorage.setItem(paneStorageKey, value) } catch { /* 本次选择仍然生效。 */ } })
watch(pane, value => emit('pane-change', value), { immediate: true })
const allMentionSessions = computed(()=>[...new Map([...props.sessions,...props.searchSessions.filter(row=>Number(row.mentionUnread)>0)].map(row=>[row.key,row])).values()])

const summaryPaneKeys = ['summary', 'notifications', 'annotation-projects', 'translation-projects', 'interpretation-projects', 'consultations']
// 手机端采用“列表 → 会话”两级导航：列表页只显示分类与会话，进入会话后只显示当前会话。
const listView = computed(() => props.mobile && props.sidebarOpen && !summaryPaneKeys.includes(pane.value))
const chatView = computed(() => props.mobile && !props.sidebarOpen && !summaryPaneKeys.includes(pane.value))
const mobileListTitle = computed(() => (pane.value === 'messages' && showMentions.value ? '@我' : panes.find(item => item.key === pane.value)?.label || '沟通'))
// 手机端底部导航：常用入口直接显示，项目类与其余入口收进弹出菜单。
const mobileProjectKeys = ['annotation-projects', 'translation-projects', 'interpretation-projects', 'consultations']
const mobileTabs = computed(() => [
  { key: 'messages', label: '消息', icon: ChatDotRound, badge: messageBadgeTotal.value },
  { key: 'contacts', label: '通讯录', icon: User, badge: 0 },
  { key: 'notifications', label: '通知', icon: Bell, badge: notificationFeed.unread.value },
])
const mobileGroups = computed(() => [
  { label: '项目', icon: Headset, items: panes.filter(item => mobileProjectKeys.includes(item.key)) },
  { label: '更多', icon: MoreFilled, items: panes.filter(item => ['summary', 'settings'].includes(item.key)) },
].filter(group => group.items.length))
const mobileGroupVisible = reactive({})
function mobileSelectPane(key) {
  projectMine.value = false; projectMenuVisible.value = false
  if (key === 'summary') summaryIssueId.value = ''
  if (key === 'notifications') notificationFeed.refresh()
  pane.value = key
  // 消息、通讯录、设置位于列表侧栏内，需要保证列表页处于打开状态。
  if (['messages', 'contacts', 'settings'].includes(key) && !props.sidebarOpen) emit('toggle-sidebar')
}
const mentionTotal = computed(() => props.messageNotificationTotal ?? mentionUnreadCount(allMentionSessions.value))
const messageBadgeTotal = computed(() => mentionTotal.value)
const notificationBadgeTotal = computed(() => notificationFeed.unread.value)
function openFolderUnread(id){
 pane.value='messages';selectedFolder.value=id;tab.value='all';annotationMode.value='mention';keyword.value='';applyKeyword();
 const target=firstUnreadMentionSession(visibleSessions.value);
 if(props.narrow&&!props.sidebarOpen)emit('toggle-sidebar');
 if(target?.messageId)emit('locate-mention',target);else if(target)emit(target.opened?'select':'open',target);
}
function badgeClick(key){selectPane(key)}
function showMentionInbox() {
  pane.value = 'messages'; selectedFolder.value = ''; tab.value = 'mention'; annotationMode.value = 'mention'
  keyword.value = ''; applyKeyword()
  if (props.narrow && !props.sidebarOpen) emit('toggle-sidebar')
}
function openUnreadMentionConversations() {
  pane.value = 'messages'; selectedFolder.value = ''; tab.value = 'all'; annotationMode.value = 'group'
  keyword.value = ''; applyKeyword()
  nextTick(() => { if (sessionList.value) sessionList.value.scrollTop = 0 })
  if (props.narrow && !props.sidebarOpen) emit('toggle-sidebar')
  const target = firstUnreadMentionSession([...allMentionSessions.value].sort((a,b)=>compareMentionSessions(a,b)))
  if (!target) return
  if(target.projectType==='direct')annotationMode.value='direct'
  if (target.messageId) emit('locate-mention', target)
  else emit(target.opened ? 'select' : 'open', target)
}
function openMobileSessions() {
  if (pane.value !== 'messages') {
    pane.value = 'messages'
    if (!props.sidebarOpen) emit('toggle-sidebar')
  } else emit('toggle-sidebar')
}
const projectMine=ref(false),projectMenuVisible=ref(false),projectMenuAnchor=ref(null),projectMenuKey=ref('')
const isProjectPane=key=>['annotation-projects','translation-projects','interpretation-projects','consultations'].includes(key)
const projectModule=key=>key==='translation-projects'?'translation':key==='interpretation-projects'?'interpretation':'consultation'
function openProjectMenu(event,key){if(!isProjectPane(key))return;event.preventDefault();event.stopPropagation();projectMenuKey.value=key;projectMenuAnchor.value=event.currentTarget;projectMenuVisible.value=true}
function selectMyProjects(){projectMenuVisible.value=false;projectMine.value=true;pane.value=projectMenuKey.value}
function selectPane(key) {
  projectMine.value=false;projectMenuVisible.value=false
  if(key==='summary')summaryIssueId.value=''
  if(key==='notifications')notificationFeed.refresh()
  if (key === 'messages' && mentionTotal.value > 0) openUnreadMentionConversations()
  else pane.value = key
}
const typeLabel = type => type === 'discussion' ? '讨论' : type === 'direct' ? '单聊' : type === 'annotation' ? '标注' : '笔译'
function contactOpened() {
  annotationMode.value = 'direct'
  tab.value = 'direct'
  selectedFolder.value = ''
  keyword.value = ''; applyKeyword()
  pane.value = 'messages'
  emit('contact-opened')
}
const groups = [{ key: 'all', label: '消息' }, { key: 'pinned', label: '置顶' }, { key: 'unread', label: '未读' }, { key: 'mention', label: '@我' }, { key: 'direct', label: '单聊' }, { key: 'starred', label: '特别关注' }, { key: 'project', label: '项目群' }, { key: 'annotation', label: '标注项目群' }, { key: 'translation', label: '笔译项目群' }, { key: 'creator', label: '我创建的' }]
const { categories } = useChatSessionCategories()
const recentClosedVisible = ref(false)
const recentMenuZ = ref(2101)
function prepareRecentMenu(event) {
  let topZ = 2100
  for (let element = event.currentTarget; element; element = element.parentElement) {
    topZ = Math.max(topZ, Number.parseInt(window.getComputedStyle(element).zIndex, 10) || 0)
  }
  recentMenuZ.value = topZ + 1
}
function restoreRecent(item) { recentClosedVisible.value = false; emit('restore-closed', item) }
function restoreAllRecent() {
  const items = props.recentClosed.slice(0, 10)
  recentClosedVisible.value = false
  // 从较早的记录开始打开，使最新关闭的会话最后成为当前会话。
  for (const item of items.reverse()) emit('restore-closed', item)
}
const recentInFolder = computed(() => props.recentClosed.filter(item => annotationMode.value === 'direct'
  ? item.projectType === 'direct' : item.projectType !== 'direct' && sessionMatchesFolder(item, selectedFolder.value, folderNodes.value)))
const renamingDiscussion = ref(null), renameSaving = ref(false), renameError = ref('')
function startDiscussionRename(session) {
  if (!categories.canManage || !canStartChatNameEditing()) return
  renamingDiscussion.value = session; renameError.value = ''
}
async function saveDiscussionName(name) {
  if (renameSaving.value || !renamingDiscussion.value) return
  renameSaving.value = true; renameError.value = ''
  try {
    const session = renamingDiscussion.value
    await chatRequest(`discussions/${session.projectId}/name`, { method: 'put', data: { name, revision: categories.items.find(item => item.id === session.projectId)?.revision } })
    renamingDiscussion.value = null; emit('categories-changed')
  } catch (error) { renameError.value = error.detail || error.message || '修改名称失败' }
  finally { renameSaving.value = false }
}
async function deleteDiscussion(session) {
  const row = categories.items.find(item => item.id === session.projectId)
  if (!row) return
  try { await ElMessageBox.confirm(`删除“${session.title}”会话？删除后停止访问，历史消息保留。`, '删除会话', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  try {
    await chatRequest(`session-categories/${row.id}`, { method: 'put', data: { active: false, revision: row.revision } })
    window.dispatchEvent(new CustomEvent('chat-conversation-access-denied', { detail: { projectType: 'discussion', projectId: row.id } }))
    emit('categories-changed')
  } catch (e) { ElMessage.error(e.detail || e.message || '删除失败') }
}
const categoryAssignment = ref()
const annotationPickerVisible = ref(false)
function joinedAnnotation(row) {
  keyword.value = ''; applyKeyword(); annotationMode.value = 'group'; pane.value = 'messages'
  const statusFolder = `status:${normalizeAnnotationStatus(row.projectStatus)}`
  selectFolder(folderNodes.value.some(node => node.id === statusFolder) ? statusFolder : annotationFolderId)
  emit('categories-changed')
}
const currentGroupLabel = computed(() => {
  const base=groups.find(group=>group.key===tab.value)?.label||categories.items.find(row=>categoryKey(row.id)===tab.value)?.name||'消息'
  const folder=annotationMode.value!=='direct'&&folderNodes.value.find(row=>row.id===selectedFolder.value)
  return folder ? `${folder.name}${tab.value==='all'?'':` · ${base}`}` : base
})
const storageKey = `xinshi.chatGroup.${localStorage.getItem('user_id') || 'anonymous'}`
let saved = 'all'
try { saved = localStorage.getItem(storageKey) || 'all' } catch { /* 存储不可用时使用默认分组。 */ }
const tab = ref(groups.some(g => g.key === saved) || saved.startsWith('category:') ? saved : 'all')
watch(() => [categories.loaded, categories.ready, categories.items.map(row => `${row.id}:${row.active}`).join(',')], ([loaded, ready]) => {
  if (loaded && tab.value.startsWith('category:') && (!ready || !categories.items.some(row => row.active && categoryKey(row.id) === tab.value))) tab.value = 'all'
})
const groupsVisible = ref(false)
const folderStorageKey = `xinshi.chatFolder.${localStorage.getItem('user_id') || 'anonymous'}`
let savedFolder = tab.value === 'annotation' ? annotationFolderId : ''
try { savedFolder = localStorage.getItem(folderStorageKey) ?? savedFolder } catch { /* 使用默认目录。 */ }
if (resourceDiscussionIds.includes(savedFolder)) savedFolder = resourceFolderId
const selectedFolder = ref(savedFolder)
const folderTreeRef=ref()
const folderNodes = computed(() => sessionFolderNodes(categories.items))
const searchMode = ref('sessions'), searchRevision = ref(0)
const searchPlaceholder = computed(() => searchMode.value === 'messages' ? '搜索全部会话的聊天记录' : '搜索全部会话：名称、订单号、消息')
watch(selectedFolder, value => { try { localStorage.setItem(folderStorageKey, value) } catch { /* 本次选择仍生效。 */ } })
watch(() => [categories.loaded, ...folderNodes.value.map(row => row.id)], ([loaded]) => { if (loaded && selectedFolder.value && !folderNodes.value.some(row => row.id === selectedFolder.value)) selectedFolder.value = categories.items.find(row => row.id === selectedFolder.value)?.parentKey === resourceFolderId ? resourceFolderId : '' }, { immediate: true })
function selectFolder(id) { tab.value = 'all'; selectedFolder.value = id }
const mentionSort = ref('time_desc'), mentionSortMenu = ref(null)
const mentionFilters = computed(() => ({ sort: mentionSort.value }))
const annotationMode = ref(tab.value === 'direct' ? 'direct' : tab.value === 'mention' ? 'mention' : 'group')
const showMentions = computed(() => annotationMode.value === 'mention' && !selectedFolder.value)
const annotationMentionView = computed(() => annotationMode.value === 'mention')
const filteredMentionTotal = ref(0)
watch(tab, () => { groupsVisible.value = false; if (tab.value === 'direct') annotationMode.value = 'direct'; else if (tab.value === 'mention') { annotationMode.value = 'mention'; selectedFolder.value = '' } })
watch(tab, value => { try { localStorage.setItem(storageKey, value) } catch { /* 本次选择仍然生效。 */ } })
function inGroup(session, key) {
  if (key.startsWith('category:')) return !!session.categoryIds?.includes(key.slice('category:'.length))
  if (key === 'all') return true
  if (key === 'creator') return !!session.isCreator
  if (key === 'project') return session.projectType !== 'direct'
  if (['direct', 'annotation', 'translation'].includes(key)) return session.projectType === key
  return !!session[key]
}
const groupCount = key => key === 'mention' ? props.mentionHistoryTotal : new Set(props.sessions.filter(s => inGroup(s, key)).map(sessionListKey)).size
const keyword = ref('')
const appliedKeyword = ref('')
let keywordTimer = 0

const applyKeyword = () => {
  window.clearTimeout(keywordTimer)
  appliedKeyword.value = keyword.value.trim().toLowerCase()
  searchRevision.value++
}

watch(keyword, (value) => {
  window.clearTimeout(keywordTimer)
  if (!value) {
    appliedKeyword.value = ''
    return
  }
  keywordTimer = window.setTimeout(applyKeyword, 400)
})

watch(searchMode, () => applyKeyword())

const sessionDisplayTime = session => annotationMentionView.value ? latestMentionAt(session) : session.lastMessage?.createdAt
const visibleSessions = computed(() => groupSessionList((appliedKeyword.value ? [...new Map([...props.searchSessions,...props.sessions].map(row=>[row.key,row])).values()] : annotationMentionView.value ? allMentionSessions.value : props.sessions).filter((session) => {
  const directMode = annotationMode.value === 'direct'
  if (!appliedKeyword.value) {
    if (directMode ? session.projectType !== 'direct' : session.projectType === 'direct') return false
    if (!directMode && !sessionMatchesFolder(session, selectedFolder.value, folderNodes.value)) return false
    if (!['all', 'annotation', 'direct', 'mention'].includes(tab.value) && !inGroup(session, tab.value)) return false
    if (annotationMentionView.value && !(Number(session.mentionHistoryCount) > 0 || Number(session.mentionUnread) > 0 || session.lastMessage?.mentionsMe)) return false
  }
  if (!appliedKeyword.value) return true
  return matchesSearch(`${session.title || ''} ${session.subtitle || ''} ${session.lastMessage?.preview || ''} ${session.lastMessage?.senderName || ''}`, appliedKeyword.value)
}).sort(compareSessionActivity), props.activeKey)
  .sort((a, b) => annotationMentionView.value ? compareMentionSessions(a, b, mentionSort.value) : compareSessionActivity(a, b)))
function syncActiveConversation(context,external=false){
 if(!context.projectId)return
 const session=props.sessions.find(row=>String(row.projectId)===String(context.projectId)&&row.projectType===context.projectType)||{...context,categoryIds:[]}
 if(!external&&pane.value!=='messages')return
 if(!external&&showMentions.value)return
 const target=activeConversationFolder(session,folderNodes.value,selectedFolder.value)
 if(external){pendingContextFolder='';pane.value='messages';keyword.value='';applyKeyword()}
 if(context.projectType==='direct'){annotationMode.value='direct';tab.value='direct';selectedFolder.value=''}
 else{if(annotationMode.value==='direct'||selectedFolder.value&&target!==selectedFolder.value||external&&!showMentions.value){annotationMode.value='group';tab.value='all'}selectedFolder.value=target}
 nextTick(()=>{folderTreeRef.value?.reveal(target);const element=sessionList.value?.querySelector('.chat-workspace__session.is-active');element?.scrollIntoView({block:'nearest'})})
}
function activateFromOutside(event){nextTick(()=>syncActiveConversation(event.detail||{},true))}
watch(()=>[props.activeKey,props.projectId,props.projectType],()=>{if(props.activeKey)syncActiveConversation({projectId:props.projectId,projectType:props.projectType})},{flush:'post'})
onMounted(()=>window.addEventListener('chat-conversation-activated',activateFromOutside))
onBeforeUnmount(()=>window.removeEventListener('chat-conversation-activated',activateFromOutside))
function showAnnotation() { pane.value = 'messages'; annotationMode.value = 'group'; selectFolder(annotationFolderId) }
function showSummary(event){pane.value='summary';summaryIssueId.value='';nextTick(()=>{summaryIssueId.value=event.detail?.issueId||''})}
let pendingContextFolder = ''
function openContextFirst() {
  if (!pendingContextFolder) return
  if (pane.value !== 'messages' || selectedFolder.value !== pendingContextFolder) { pendingContextFolder = ''; return }
  const first = visibleSessions.value[0]
  if (!first) return
  pendingContextFolder = ''
  emit(first.opened ? 'select' : 'open', first)
  nextTick(() => { if (sessionList.value) sessionList.value.scrollTop = 0 })
}
function openContextConversations(context) {
  const folder = folderNodes.value.find(row => !row.parentKey && row.ruleKey === context)
  if (!folder) { pane.value = 'messages'; return }
  pane.value = 'messages'; annotationMode.value = 'group'; tab.value = 'all'
  keyword.value = ''; applyKeyword(); selectedFolder.value = folder.id
  nextTick(()=>folderTreeRef.value?.reveal(folder.id))
  pendingContextFolder = folder.id
  // 该组为空时不展示上次其他板块的会话；目录异步加载后再选第一条。
  emit('context-empty')
  openContextFirst()
}
watch(() => props.sessions, openContextFirst)
function showHeaderMessages(event) { pendingContextFolder = ''; if (event.detail?.context) openContextConversations(event.detail.context); else if (event.detail?.mentions) openUnreadMentionConversations(); else pane.value = 'messages' }
onMounted(() => window.addEventListener('chat-topic-show-annotation', showAnnotation))
onMounted(() => window.addEventListener('chat-show-messages', showHeaderMessages))
const showConversationNotifications = () => selectPane('notifications')
onMounted(() => window.addEventListener('chat-show-notifications', showConversationNotifications))
onBeforeUnmount(() => window.removeEventListener('chat-show-notifications', showConversationNotifications))
onMounted(()=>window.addEventListener('chat-open-summary',showSummary))
onBeforeUnmount(()=>window.removeEventListener('chat-open-summary',showSummary))
onBeforeUnmount(() => { window.clearTimeout(keywordTimer); window.removeEventListener('chat-topic-show-annotation', showAnnotation); window.removeEventListener('chat-show-messages', showHeaderMessages) })
</script>
<style scoped>
.chat-workspace__session-left{display:flex;flex:none;align-self:stretch;flex-direction:column;align-items:center;justify-content:flex-start;gap:8px;width:38px;padding-top:1px}.chat-workspace__session-left>.chat-workspace__avatar:only-child{margin-top:8px}.chat-session-member-count{position:relative;left:-6px;flex:none;display:inline-flex;align-items:center;padding:1px 4px;border-radius:4px;background:#e8eef5;color:#64748b;font-size:10px;font-weight:500;line-height:16px;white-space:nowrap}

.chat-workspace__topic-panel{flex:1;min-height:0;overflow-y:auto;padding:8px}
.chat-workspace__recent-closed{flex:none;padding:4px 10px;border-bottom:1px solid #e6eaf0}
.chat-recent-closed{max-height:min(440px,calc(100vh - 120px));overflow-y:auto}
.chat-recent-closed__item{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #edf1f5}
.chat-recent-closed__item>span{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
.chat-recent-closed__item strong{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-recent-closed__item small,.chat-discussion-protected{color:#94a3b8;font-size:11px}
.chat-workspace__close-button{position:absolute;z-index:2;right:8px;top:8px;display:flex;align-items:center;justify-content:center;width:36px;height:36px;box-sizing:border-box;padding:0;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;color:#334155;font:26px/1 Arial,sans-serif;cursor:pointer;opacity:1;visibility:visible}.chat-workspace__close-button:hover{color:#dc2626;border-color:#fca5a5;background:#fef2f2}.chat-workspace__close-button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:2px}
.chat-recent-closed__tools{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid #edf1f5;font-size:12px}
.chat-session-orders .el-button{max-width:100%;font-size:11px;white-space:normal;text-align:left}
.chat-session-order-options{display:flex;flex-direction:column;align-items:flex-start;gap:10px;max-height:320px;overflow-y:auto}
.chat-session-order-options .el-button{margin:0;white-space:normal;text-align:left}
.chat-workspace__annotation-filters{flex:none;padding:0 12px 10px;border-bottom:1px solid #e6eaf0}
.chat-session-mention-history{color:#64748b;font-size:11px}
.chat-workspace__annotation-filters button{border:1px solid #dce3ed;border-radius:5px;background:#fff;color:#475569;padding:5px 7px;font:inherit;font-size:12px;cursor:pointer}
.chat-workspace__annotation-filters button.is-active{background:var(--color-primary-soft);border-color:#cbd5e1;color:var(--color-primary-hover)}
.chat-workspace__annotation-filters button.has-unread-mention{color:#b91c1c;border-color:#f2b8b8;background:#fff1f2}
.chat-workspace__annotation-filters button.has-unread-mention.is-active{border-color:#b91c1c;box-shadow:inset 0 0 0 1px #b91c1c}
.chat-workspace__annotation-filters button:focus-visible{outline:2px solid var(--color-primary);outline-offset:1px}
.chat-workspace__annotation-mode{display:flex;gap:6px;margin-top:10px}
.chat-workspace__annotation-mode button{flex:1}
.chat-workspace__session.has-unread-mention .chat-workspace__session-title strong{color:#b91c1c}
.chat-workspace__frame{position:relative;display:flex;width:100%;height:100%;min-height:0;flex-direction:column}
.chat-workspace__header{display:flex;box-sizing:border-box;height:52px;min-height:52px;padding:0 12px;align-items:center;gap:12px;border-bottom:1px solid #e6eaf0;background:white;cursor:grab;user-select:none}
.chat-workspace__header--dragging{cursor:grabbing}.chat-workspace__header--pinned{cursor:default}
.chat-workspace__heading{display:flex;align-items:center;gap:8px;min-width:0;flex:1;cursor:text;user-select:text}.chat-workspace__heading strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px}.chat-workspace__heading .el-tag{flex:none}.chat-workspace__subtitle{font-size:12px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chat-workspace__actions,.chat-header-session-tools{display:flex;align-items:center;gap:2px;flex:none}.chat-workspace__actions :deep(.el-button){margin:0;width:28px;height:28px;padding:4px;flex:none}.chat-header-divider{width:1px;height:20px;background:#e2e8f0;margin:0 6px}
.chat-workspace__body{display:flex;min-height:0;flex:1}.chat-workspace__sessions{display:flex;min-width:0;min-height:0;flex:none;flex-direction:column;overflow:hidden;box-sizing:border-box;border-right:1px solid #e6eaf0;background:#f9fafc}.chat-workspace__brand{display:flex;align-items:center;justify-content:space-between;height:52px;flex:none;padding:0 16px;box-sizing:border-box}.chat-workspace__brand small{font-size:11px;color:#94a3b8}
.chat-workspace__pane-tabs{display:flex;padding:8px;gap:4px;flex:none}.chat-workspace__pane-tabs button{display:flex;flex:1;align-items:center;justify-content:center;gap:4px;min-width:0;border:0;border-radius:6px;padding:7px 2px;font:inherit;font-size:12px;color:#64748b;background:transparent;cursor:pointer;white-space:nowrap}.chat-workspace__pane-tabs .is-active{background:var(--color-primary-soft);color:var(--color-primary-hover);font-weight:600}.chat-pane-count{min-width:16px;padding:0 5px;border-radius:8px;background:#ef4444;color:#fff;font-size:10px;line-height:16px}
.chat-workspace__session-tools{display:flex;align-items:center;gap:4px;padding:8px 10px;flex:none;min-width:0}.chat-workspace__search{flex:1;min-width:0}.chat-workspace__tabs{flex:none;min-width:0}.chat-workspace__tabs .el-button{padding:4px;font-size:12px}.chat-workspace__filter{max-width:108px}.chat-workspace__filter-label{display:inline-block;max-width:64px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}.chat-workspace__list{flex:1;min-height:0;overflow-y:auto;padding:4px 6px 10px}
.chat-workspace__session{position:relative;display:flex;box-sizing:border-box;width:100%;min-height:72px;padding:12px 8px;align-items:center;gap:10px;border-radius:8px;color:#334155;cursor:pointer;font:inherit}.chat-workspace__session.is-pinned{background:#f0f2f5}.chat-workspace__session:hover{background:#edf1f7}.chat-workspace__session.is-active{background:var(--color-primary-soft)}.chat-workspace__session:focus-visible{outline:2px solid var(--color-primary);outline-offset:-2px}
.chat-workspace__avatar{position:relative;display:grid;flex:none;place-items:center;width:38px;height:38px;border-radius:10px;background:#deebff;color:#4979bd;font-size:17px}.chat-workspace__avatar--annotation{width:34px;height:34px;border-radius:9px;background:#dbf1e9;color:#2a8870;font-size:15px}.chat-workspace__avatar--direct{border-radius:50%;background:#ece6fa;color:#8268b1}.chat-workspace__avatar small{position:absolute;bottom:-6px;right:-3px;padding:1px 3px;border:2px solid #f9fafc;border-radius:4px;background:#fff;color:#64748b;font-size:8px;line-height:12px}
.chat-workspace__session-main{display:flex;min-width:0;flex:1;flex-direction:column;gap:8px}.chat-workspace__session-title,.chat-workspace__preview-row{display:flex;align-items:center;gap:5px;min-width:0}.chat-workspace__session-title strong{font-size:13px;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chat-workspace__session-title time{flex:none;font-size:10px;color:#94a3b8;pointer-events:none}.chat-session-star{color:#d2a235;font-size:12px}.chat-session-preview{display:block;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:#8b96a6}.chat-session-unread{flex:none;min-width:16px;box-sizing:border-box;padding:1px 5px;border-radius:10px;background:#ef6262;color:white;font-size:10px;text-align:center}.chat-mention-label{color:#dc2626}.chat-mention-preview{margin-right:4px;padding:0 3px;border-radius:3px;background:#fef3c7;color:#92400e}.chat-session-pin{position:absolute;top:3px;left:4px;font-size:9px;color:#94a3b8}
.chat-workspace__session-controls{display:flex;flex:none;flex-direction:column;align-items:flex-end;justify-content:space-between;align-self:stretch;gap:8px}.chat-workspace__session-controls .el-button{margin:0}.chat-workspace__session-close{font-size:11px;padding:5px 7px;min-height:28px}
.chat-workspace__stage{min-width:0;flex:1;background:#f6f8fb}.chat-workspace__empty{display:flex;height:100%;align-items:center;justify-content:center;flex-direction:column;gap:14px;color:#94a3b8;font-size:13px}.chat-workspace__empty .el-icon{font-size:44px;color:#c5d2e6}.chat-workspace__empty strong{font-weight:500;font-size:17px;color:#64748b}.chat-workspace__error{padding:8px 12px;color:#b91c1c;font-size:12px}.chat-workspace__topic-panel{flex:1;min-height:0;overflow-y:auto;padding:8px}
.chat-workspace__rail{display:flex;width:56px;box-sizing:border-box;flex:none;flex-direction:column;align-items:center;gap:12px;padding:16px 4px;border-right:1px solid #e6eaf0;background:#eef2f8}.chat-workspace__user-avatar{display:grid;place-items:center;width:32px;height:32px;margin-bottom:14px;border-radius:10px;background:#5479be;color:white;font-size:14px}.chat-workspace__rail button{display:flex;flex-direction:column;align-items:center;gap:6px;width:44px;padding:10px 0;border:0;border-radius:8px;background:transparent;color:#8190a5;cursor:pointer}.chat-workspace__rail button.is-active{background:#e0e9fb;color:#4776c0}.chat-workspace__rail .el-icon{font-size:21px}.chat-workspace__rail small{font-size:10px}.chat-workspace__rail :deep(.el-badge__content){font-size:9px;height:15px;line-height:15px;padding:0 4px}
.chat-workspace--maximized:not(.chat-workspace--narrow){display:grid;grid-template-columns:56px var(--chat-session-width) minmax(0,1fr);grid-template-rows:52px minmax(0,1fr)}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__body{display:contents}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__rail{grid-column:1;grid-row:1 / 3}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__sessions{grid-column:2;grid-row:1 / 3}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__header{grid-column:3;grid-row:1}.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__stage{grid-column:3;grid-row:2}
.chat-workspace--narrow .chat-workspace__sessions{position:absolute;z-index:1;top:52px;bottom:0;left:0;max-width:calc(100% - 16px);box-shadow:var(--el-box-shadow-light)}.chat-workspace--narrow .chat-workspace__header{padding:0 6px;gap:4px}.chat-workspace--narrow .chat-workspace__heading strong{font-size:12px}.chat-workspace--narrow .chat-header-divider{margin:0 2px}.chat-workspace--narrow .chat-workspace__subtitle{display:none}.chat-workspace--narrow .chat-workspace__actions{gap:0}
.chat-max-icon{display:inline-block;width:12px;height:12px;box-sizing:border-box;border:1.5px solid currentColor;border-radius:1px}.chat-max-icon--restore{position:relative;border-color:transparent}.chat-max-icon--restore::before,.chat-max-icon--restore::after{content:'';position:absolute;width:8px;height:8px;box-sizing:border-box;border:1.5px solid currentColor;background:white}.chat-max-icon--restore::before{left:0;bottom:0}.chat-max-icon--restore::after{top:0;right:0}
.chat-session-groups{display:flex;flex-direction:column;align-items:stretch;max-height:400px;overflow:auto}.chat-session-groups .el-button{margin:0;justify-content:flex-start;padding:8px}
.chat-workspace__header{position:relative;padding-right:52px}.chat-workspace__actions{min-width:0;flex-shrink:1;overflow-x:auto;scrollbar-width:none}.chat-workspace__actions::-webkit-scrollbar{display:none}
.chat-workspace__exit-button{flex:none;margin:0;font-size:11px;padding:6px 8px}.chat-workspace__close-button:disabled{opacity:.4;cursor:not-allowed}
.chat-session-unread-dot{display:inline-block;flex:none;width:6px;height:6px;border-radius:50%;background:#a7b4c6;margin:0 4px}
</style>

<style scoped>

.chat-workspace__header{height:112px;min-height:112px;display:flex;flex-wrap:wrap;align-content:center;gap:5px 8px;padding-top:5px;padding-bottom:5px}
.chat-workspace__heading{flex:0 0 100%;height:64px;align-items:flex-start;overflow:hidden}
.chat-workspace__heading>.chat-order-identity{flex:1}.chat-workspace__heading>.el-tag{margin-top:2px}
.chat-workspace__actions{flex:1;justify-content:flex-end}
.chat-workspace--maximized:not(.chat-workspace--narrow){grid-template-rows:112px minmax(0,1fr)}
.chat-workspace--narrow .chat-workspace__sessions{top:112px}
</style>

<style scoped>
.chat-multi-entry{flex:none;margin:0!important;font-size:11px;padding:6px 8px}</style>

<style scoped src="./chatHeader.css" />
<style scoped>

.chat-workspace--summary .chat-workspace__stage{display:flex;flex-direction:column;min-height:0;overflow:hidden}.chat-summary-content{flex:1;min-height:0;overflow:auto;padding:12px;background:white}.chat-workspace--summary.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__stage,.chat-workspace--summary.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__header{grid-column:2 / 4}
</style>

<style scoped>
.chat-workspace__search{display:flex;gap:4px}.chat-search-mode{flex:none;width:90px}.chat-rename-button{font-size:10px;padding:2px 4px;min-height:20px}.chat-compact-rename{width:150px;max-width:100%}
.chat-workspace--compact-header .chat-workspace__header{display:flex;flex-wrap:nowrap;height:48px;min-height:48px;padding:8px 12px;gap:12px}
.chat-workspace--compact-header .chat-workspace__heading{flex:1;min-width:0;height:24px;align-self:center}
.chat-workspace--compact-header .chat-fixed-window-controls{flex:none;margin-left:auto}
.chat-workspace--compact-header.chat-workspace--maximized:not(.chat-workspace--narrow){grid-template-rows:48px minmax(0,1fr)}
</style>

<style>
.chat-search-mode-options{z-index:100030!important}
</style>

<style scoped>
/* 手机端：仿微信的两级导航。列表页全屏显示分类与会话，点击后仅显示当前会话，左上角返回。 */
.chat-workspace--mobile{background:#fff}
.chat-workspace--mobile .chat-workspace__header{position:relative;display:flex;flex-wrap:nowrap;align-items:center;gap:2px;height:52px;min-height:52px;padding:0 6px;border-bottom:1px solid #e6eaf0;cursor:default}
.chat-workspace--mobile .chat-workspace__header>.el-button{flex:none;width:36px;height:36px;margin:0;padding:6px;font-size:20px}
.chat-workspace--mobile .chat-workspace__heading{display:block;flex:1 1 auto;min-width:0;height:auto;overflow:hidden;align-self:center}
.chat-workspace--mobile .chat-workspace__heading>strong{display:block;font-size:17px;font-weight:600;line-height:28px;padding-left:6px}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-order-identity){display:block;min-width:0}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-order-identity__title){height:22px;font-size:15px;font-weight:600;line-height:22px}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-order-identity__details){height:18px;margin-top:0;overflow:hidden;font-size:11px;line-height:18px}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-project-managers){display:none}
.chat-workspace--mobile .chat-header-command-row{flex:none;height:36px;overflow:visible;background:transparent}
.chat-workspace--mobile .chat-fixed-window-controls{flex:none;height:36px;margin-left:0;background:transparent}
.chat-workspace--mobile .chat-fixed-window-controls>button[aria-label="最小化会话窗口"],
.chat-workspace--mobile .chat-fixed-window-controls>button[aria-label="最大化会话窗口"],
.chat-workspace--mobile .chat-fixed-window-controls>button[aria-label="还原会话窗口"]{display:none}
.chat-workspace--chat .chat-fixed-window-controls>button[aria-label="退出整个会话窗口"]{display:none}
.chat-workspace--mobile .chat-workspace__body{min-height:0}
.chat-workspace--mobile .chat-workspace__sessions{position:static;top:auto;flex:1 1 auto;width:100%!important;max-width:none;border-right:0;background:#fff;box-shadow:none}
.chat-workspace--list .chat-workspace__stage{display:none}
.chat-workspace--mobile .chat-workspace__session-tools{padding:8px 10px 6px}
.chat-workspace--mobile .chat-search-mode{width:78px}
.chat-workspace--mobile .chat-workspace__filter-label{display:none}
.chat-workspace--mobile .chat-workspace__annotation-filters{padding:0 10px 6px;border-bottom:0}
.chat-workspace--mobile .chat-workspace__annotation-mode{margin-top:4px}
.chat-workspace--mobile .chat-workspace__annotation-mode button{padding:7px 0;font-size:13px}
.chat-workspace--mobile .chat-workspace__recent-closed{display:none}
.chat-workspace--mobile .chat-workspace__list{padding:0 0 6px;background:#fff}
.chat-workspace--mobile .chat-workspace__session{min-height:72px;padding:10px 12px;gap:12px;border-bottom:1px solid #f1f3f6;border-radius:0}
.chat-workspace--mobile .chat-workspace__session:hover,.chat-workspace--mobile .chat-workspace__session.is-active{background:transparent}
.chat-workspace--mobile .chat-workspace__session.is-pinned{background:#f7f7f7}
.chat-workspace--mobile .chat-workspace__session:active{background:#ececec}
.chat-workspace--mobile .chat-workspace__session-left{width:48px;padding-top:0;align-self:center}
.chat-workspace--mobile .chat-session-member-count{display:none}
.chat-workspace--mobile .chat-workspace__avatar,.chat-workspace--mobile .chat-workspace__avatar--annotation{width:48px;height:48px;border-radius:6px;font-size:20px}
.chat-workspace--mobile .chat-workspace__session-left>.chat-workspace__avatar:only-child{margin-top:0}
.chat-workspace--mobile .chat-workspace__session-main{gap:4px}
.chat-workspace--mobile .chat-workspace__session-title strong{font-size:16px;font-weight:500;color:#111}
.chat-workspace--mobile .chat-workspace__session-title time{font-size:12px}
.chat-workspace--mobile .chat-session-preview{font-size:13px;color:#8a8a8a}
.chat-workspace--mobile .chat-workspace__session-controls{align-self:center}
.chat-workspace--mobile .chat-workspace__pane-tabs{display:none}
.chat-workspace--mobile .chat-workspace__stage{background:#fff}
.chat-workspace--mobile.chat-workspace--summary .chat-workspace__stage{flex:1}
.chat-mobile-tabbar{display:flex;flex:none;align-items:stretch;border-top:1px solid #e5e5e5;background:#f7f7f7;padding-bottom:env(safe-area-inset-bottom)}
.chat-mobile-tabbar>button,.chat-mobile-tabbar>.el-tooltip__trigger{flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;height:54px;padding:4px 0;border:0;background:transparent;color:#5c5c5c;font:inherit;font-size:11px;cursor:pointer}
.chat-mobile-tabbar .el-icon{font-size:24px}
.chat-mobile-tabbar .is-active{color:#07c160}
.chat-mobile-tabbar :deep(.el-badge__content){font-size:10px;height:16px;line-height:16px;padding:0 5px}
</style>
<style>
.chat-mobile-group-popover{padding:6px!important}
.chat-mobile-group{display:flex;flex-direction:column}
.chat-mobile-group button{height:44px;border:0;border-bottom:1px solid #f1f3f6;background:transparent;color:#334155;font:inherit;font-size:15px;text-align:left;padding:0 12px;cursor:pointer}
.chat-mobile-group button:last-child{border-bottom:0}
.chat-mobile-group button.is-active{color:#07c160;font-weight:600}
</style>

<style scoped>
.chat-workspace__rail{min-height:0;overflow-y:auto}.chat-workspace__rail>button,.chat-workspace__user-avatar{flex-shrink:0}
</style>
