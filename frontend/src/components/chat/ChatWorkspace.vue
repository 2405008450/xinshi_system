<template>
  <div class="chat-workspace__frame" :class="{ 'chat-workspace--maximized': maximized, 'chat-workspace--middle-list': middleList, 'chat-workspace--wide-header': wideHeader, 'chat-workspace--narrow': narrow, 'chat-workspace--mobile': mobile, 'chat-workspace--list': listView, 'chat-workspace--chat': chatView, 'chat-workspace--compact-header': pane === 'summary','chat-workspace--summary':['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane) }" :style="{ '--chat-session-width': `${narrow ? 0 : sessionWidth}px` }">
    <header class="chat-workspace__header" :class="{ 'chat-workspace__header--dragging': dragging, 'chat-workspace__header--pinned': maximized }" @mousedown="emit('header-mousedown', $event)" @dblclick="emit('header-dblclick', $event)">
      <el-button v-if="narrow && !listView" link :aria-label="mobile ? '返回会话列表' : '会话列表'" :title="messageBadgeTotal ? `${messageBadgeTotal} 条未读 @我，点击查看会话列表` : (mobile ? '返回会话列表' : '会话列表')" @click="openMobileSessions"><el-badge :value="messageBadgeTotal" :max="99" :hidden="!messageBadgeTotal"><el-icon><ArrowLeft v-if="mobile" /><ChatDotRound v-else /></el-icon></el-badge></el-button>
      <div class="chat-workspace__heading" @mousedown.stop @dblclick.stop>
        <ChatOrderIdentity v-if="!listView && !['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane) && ['annotation', 'translation'].includes(projectType) && subtitle" :title="title" :order-no="subtitle" :project-type="projectType" :project-id="projectId" show-managers>
          <template v-if="projectType === 'annotation' && pane === 'messages'" #filters>
            <ChatAnnotationFilters v-bind="annotationFilters" @change="emit('annotation-filters', $event)" />
          </template>
        </ChatOrderIdentity>
        <strong v-else :title="title">{{ listView ? mobileListTitle : pane==='summary'?'总结':pane==='notifications'?'通知':isProjectPane(pane)?`${projectMine ? '我的' : ''}${panes.find(item=>item.key===pane)?.label || ''}`:title || '沟通' }}</strong>
        <el-tag v-if="projectType && !narrow" size="small" effect="plain">{{ typeLabel(projectType) }}</el-tag>
        <span v-if="projectType === 'direct' && subtitle && subtitle !== '内部私聊'" class="chat-workspace__subtitle">{{ subtitle }}</span>
      </div>
      <div v-show="pane !== 'summary' && !listView" class="chat-header-command-row" title="横向滚动查看更多操作" @mousedown.stop>

      <div class="chat-workspace__actions">
        <el-button v-if="activeSession && !narrow" link class="chat-workspace__quick-action" :class="{ 'is-active': activeSession.pinned }" :aria-label="activeSession.pinned ? '取消置顶会话' : '置顶会话'" :title="activeSession.pinned ? '取消置顶' : '置顶当前会话'" @click="emit('preference', { session: activeSession, data: { pinned: !activeSession.pinned } })"><el-icon><Top /></el-icon></el-button>
        <el-button v-if="activeSession && !narrow" link class="chat-workspace__quick-action" :class="{ 'is-starred': activeSession.starred }" :aria-label="activeSession.starred ? '取消收藏会话' : '收藏会话'" :title="activeSession.starred ? '取消收藏' : '收藏当前会话，方便在收藏夹快速找到'" @click="emit('preference', { session: activeSession, data: { starred: !activeSession.starred } })"><el-icon><StarFilled v-if="activeSession.starred" /><Star v-else /></el-icon></el-button>
        <el-button v-if="activeSession && !narrow" link class="chat-workspace__quick-action" :class="{ 'is-unread': hasSessionUnread(activeSession) }" :aria-label="hasSessionUnread(activeSession) ? '标为已读' : '标为未读'" :title="hasSessionUnread(activeSession) ? '标为已读' : '标为未读，方便后续快速定位'" @click="emit('preference', { session: activeSession, data: hasSessionUnread(activeSession) ? { markRead: true } : { markUnread: true } })"><el-icon><Message /></el-icon></el-button>
        <ChatConversationMore :project-id="projectId" :project-type="projectType" :can-duplicate="['annotation','translation'].includes(projectType) && !!activeKey" @duplicate="emit('duplicate-window')" @multiple="emit('open-multiple')">
          <div id="chat-workspace-session-tools" class="chat-header-session-tools" />
        <ChatConversationParticipants menu-layout v-if="['translation', 'discussion'].includes(projectType) && projectId" :key="`${projectType}:${projectId}`" :project-id="projectId" :project-type="projectType" />
          <AnnotationChatInbox menu-layout @conversation-opened="pane='messages'" @navigate="emit('project-navigate')" />
        </ChatConversationMore>
        <el-button v-if="activeKey && !narrow" link aria-label="固定小窗" title="固定当前小窗，边聊边工作" @click="emit('pin')"><el-icon><ChatPinIcon /></el-icon></el-button>
        <div id="chat-workspace-session-close" class="chat-header-session-close" />
        <span class="chat-header-divider" />
      </div>
      </div>
      <ChatWindowControls :project-id="projectId" :project-type="projectType" :show-entry="pane !== 'summary' && !listView" :show-search="pane !== 'summary' && !!activeKey && !listView" :show-resize="!mobile" :show-exit="!chatView" :maximized="maximized" :order-no="subtitle" @navigate="emit('project-navigate')" @search="emit('open-search')" @minimize="emit('minimize')" @maximize="emit('toggle-maximize')" @restore="emit('normal-size')" @exit="emit('exit-workspace')" />
    </header>
    <div class="chat-workspace__body">
      <nav v-if="maximized && !narrow" class="chat-workspace__rail" aria-label="沟通导航">
        <span class="chat-workspace__user-avatar" title="我的沟通">{{ chatAvatarText(currentUserName) }}</span>
        <button v-for="item in panes" :key="item.key" type="button" :title="item.key === 'messages' && mentionTotal ? `${mentionTotal} 条未读提及，点击查看` : item.label" :aria-label="item.label" :aria-pressed="pane === item.key" :class="{ 'is-active': pane === item.key }" @click="selectPane(item.key)" @contextmenu="openProjectMenu($event,item.key)" @keydown.shift.f10="openProjectMenu($event,item.key)">
          <el-badge :value="item.key === 'notifications' ? notificationBadgeTotal : messageBadgeTotal" :max="99" :hidden="item.key === 'notifications' ? !notificationBadgeTotal : item.key !== 'messages' || !messageBadgeTotal" @click.stop="badgeClick(item.key)"><el-icon><component :is="item.icon" /></el-icon></el-badge><small>{{ item.shortLabel || item.label }}</small>
        </button>
      </nav>
      <aside v-show="!['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane) && (!narrow || sidebarOpen)" class="chat-workspace__sessions" @dragover="sessionPanelDragOver" @drop="dropSessionPanel($event, 'bottom')" :style="{ width: `${sessionWidth}px` }">
        <div v-if="!maximized || narrow" class="chat-workspace__pane-tabs" role="tablist" aria-label="沟通导航"><button v-for="item in panes" :key="item.key" type="button" :aria-label="item.label" :aria-pressed="pane === item.key" :class="{ 'is-active': pane === item.key }" @click="selectPane(item.key)" @contextmenu="openProjectMenu($event,item.key)" @keydown.shift.f10="openProjectMenu($event,item.key)"><span>{{ item.shortLabel || item.label }}</span><b v-if="item.key === 'messages' && mentionTotal" class="chat-mention-label">@</b><span v-if="item.key === 'notifications' && notificationBadgeTotal" class="chat-pane-count" @click.stop="badgeClick(item.key)">{{ notificationBadgeTotal > 99 ? '99+' : notificationBadgeTotal }}</span><span v-if="item.key === 'messages' && messageBadgeTotal" class="chat-pane-count">{{ messageBadgeTotal > 99 ? '99+' : messageBadgeTotal }}</span></button></div>
        <div v-else class="chat-workspace__brand">
          <div class="chat-workspace__brand-title">
            <strong>{{ pane === 'messages' && (showMentions || annotationMentionView) ? (annotationMode === 'mention-all' ? '@所有人' : showMentions ? '@我' : '提及') : panes.find(item => item.key === pane)?.label }}</strong>
            <small>{{ pane === 'messages' ? showMentions ? `${filteredMentionTotal} 条提及` : '' : pane === 'contacts' ? '内部通讯录' : '' }}</small>
          </div>
          <button v-if="!narrow" type="button" class="chat-workspace__split-reset" title="恢复左右区域的默认宽度" @click="emit('split-reset')">默认宽</button>
        </div>
        <template v-if="pane === 'messages'">
          <div class="chat-workspace__session-tools">
            <div class="chat-workspace__search" :title="searchMode === 'messages' ? '搜索聊天记录关键词' : '搜索会话名称、订单号'" data-auto-draft="off"><el-input v-model="keyword" clearable :placeholder="searchPlaceholder" @keyup.enter="applyKeyword"><template #prepend><el-select v-model="searchMode" class="chat-search-mode" popper-class="chat-search-mode-options" aria-label="搜索范围"><el-option label="会话" value="sessions" /><el-option label="聊天记录" value="messages" /></el-select></template><template #prefix><button type="button" class="chat-search-submit" aria-label="查询会话" title="查询" @click="applyKeyword"><el-icon><Search /></el-icon></button></template></el-input></div>
            <div class="chat-workspace__tabs">
              <el-popover ref="groupPicker" v-model:visible="groupsVisible" title="会话分组筛选" :draft-filter="false" trigger="click" placement="bottom-end" :width="280" popper-class="chat-session-popover">
                <template #reference><el-button class="chat-workspace__filter" :class="{ 'is-active': tab !== 'all' }" :aria-label="`会话分组 ${currentGroupLabel}`" :title="`分组筛选：${currentGroupLabel}`"><el-icon><Filter /></el-icon><span v-if="tab !== 'all'" class="chat-workspace__filter-dot" aria-hidden="true" /></el-button></template>
                <div class="chat-session-groups">
                  <template v-for="group in groups" :key="group.key">
                    <div v-if="group.key === 'mention'" class="chat-session-group-row">
                      <el-button link :type="tab === 'mention' && !selectedMentionSender ? 'primary' : ''" @click="tab = 'mention'; selectedMentionSender = ''; groupPicker?.minimize()">{{ group.label }} ({{ groupCount(group.key) }})</el-button>
                      <button v-if="globalMentionSenders.items.value.length" type="button" class="chat-session-group-toggle" :aria-expanded="filterMentionExpanded" :aria-label="`${filterMentionExpanded ? '收起' : '展开'}按提及人筛选`" @click.stop="filterMentionExpanded = !filterMentionExpanded"><el-icon><ArrowDown v-if="filterMentionExpanded" /><ArrowRight v-else /></el-icon></button>
                    </div>
                    <div v-if="group.key === 'mention' && filterMentionExpanded && globalMentionSenders.items.value.length" class="chat-session-group-sub">
                      <el-button v-for="person in globalMentionSenders.items.value" :key="person.userId" link :type="annotationMode === 'mention' && selectedMentionSender === person.userId ? 'primary' : ''" @click="openMentionSender(person.userId, true)">
                        <span>{{ person.name }} ({{ person.count }})</span>
                        <b v-if="person.unreadCount" class="chat-session-group-unread">{{ person.unreadCount > 99 ? '99+' : person.unreadCount }}</b>
                      </el-button>
                    </div>
                    <el-button v-else-if="group.key !== 'mention'" link :type="tab === group.key ? 'primary' : ''" @click="tab = group.key; selectedMentionSender = ''; groupPicker?.minimize()">{{ group.label }} ({{ groupCount(group.key) }})</el-button>
                  </template>
                </div>
              </el-popover>
            </div>
          </div>
          <div class="chat-workspace__annotation-filters">
            <div class="chat-workspace__annotation-mode" role="group" aria-label="消息范围">
              <button type="button" :aria-pressed="annotationMode === 'group'" :class="{ 'is-active': annotationMode === 'group' }" @click="annotationMode = 'group'">群聊</button>
              <button type="button" :aria-pressed="annotationMode === 'direct'" :class="{ 'is-active': annotationMode === 'direct' }" @click="annotationMode = 'direct'">私聊</button>
              <button type="button" :aria-pressed="annotationMode === 'mention'" :class="{ 'is-active': annotationMode === 'mention' }" @click="openMentionInbox('mention')" @contextmenu="mentionSortMenu?.open($event)" @keydown.shift.f10="mentionSortMenu?.open($event)">@我</button>
              <button type="button" :aria-pressed="annotationMode === 'mention-all'" :class="{ 'is-active': annotationMode === 'mention-all' }" @click="openMentionInbox('mention-all')" @contextmenu="mentionSortMenu?.open($event)" @keydown.shift.f10="mentionSortMenu?.open($event)">@所有人</button>
            </div>
            <el-button v-if="annotationMode === 'group' && annotationFiltersActive && projectType !== 'annotation'"
              link @click="emit('annotation-filters', { mine: false, statuses: [] })">清除标注项目筛选</el-button>
          </div>
          <ChatSessionFolderTree ref="folderTreeRef" :compact="mobile" v-if="annotationMode !== 'direct'" :selected="selectedFolder" :active="active" :sessions="allMentionSessions" @select="selectFolder" @unread="openFolderUnread" @changed="emit('categories-changed')" @browse-annotation="annotationPickerVisible = true" @open-conversation="emit('open', $event)" />
          <div class="chat-session-bottom-target" :class="{ 'is-drop-target': panelDragging }" @dragover.prevent @drop.prevent="dropSessionPanel($event, 'bottom')">拖到这里，放回分组下方</div>
          <Teleport :to="middleHost || 'body'" :disabled="!middleList || !middleHost">
          <section class="chat-session-panel" aria-label="会话列表区域">
          <div v-if="!narrow && !mobile" class="chat-session-panel__grip" draggable="true" @dragstart="startSessionPanelDrag" @dragend="panelDragging = false" title="拖到分组与聊天之间，或拖回分组下方">
            <span>⠿</span><button type="button" @click="setPanelPlacement(middleList ? 'bottom' : 'middle')">{{ middleList ? '移回下方' : '移至中间' }}</button>
          </div>
          <div class="chat-workspace__recent-closed" role="group" aria-label="会话列表范围">
            <el-button text size="small" :type="sessionScope === 'all' ? 'primary' : ''" :aria-pressed="sessionScope === 'all'" @click="setSessionScope('all')">全部会话</el-button>
            <el-button text size="small" :type="sessionScope === 'recent' ? 'primary' : ''" :aria-pressed="sessionScope === 'recent'" @click="setSessionScope('recent')">近期会话</el-button>

            <AnnotationChatInbox menu-layout @conversation-opened="pane='messages'" @navigate="emit('project-navigate')" />
            <el-button text size="small" :type="sessionScope === 'mine' ? 'primary' : ''" :aria-pressed="sessionScope === 'mine'" @click="setSessionScope('mine')">我的项目</el-button>
            <el-popover title="会话详情" v-model:visible="recentClosedVisible" :z-index="recentMenuZ" trigger="click" placement="right-start" :width="300">
              <template #reference><el-button text size="small" @click="prepareRecentMenu" :title="`最近关闭（${recentInFolder.length}）`">最近关闭</el-button></template>
              <div class="chat-recent-closed" aria-label="最近关闭的会话">
                <div class="chat-recent-closed__tools"><span>最新关闭的会话</span><el-button link type="primary" :disabled="!recentClosed.length" @click="restoreAllRecent">一键恢复全部（{{ recentClosed.length }}）</el-button></div>
                <el-button link type="danger" :disabled="!recentClosed.length" @click="clearRecentHistory">清空全部记录</el-button>
                <p v-if="!recentInFolder.length">当前分组暂无关闭记录</p>
                <div v-for="item in pagedRecentClosed" :key="item.key" class="chat-recent-closed__item">
                  <span :title="item.title"><strong>{{ item.title }}</strong><small>{{ item.subtitle || typeLabel(item.projectType) }}</small></span>
                  <el-button link type="primary" :aria-label="`恢复 ${item.title}`" @click="restoreRecent(item)">恢复</el-button>
                  <el-button link type="danger" :aria-label="`移除关闭记录 ${item.title}`" @click="emit('remove-closed-history',item)">移除记录</el-button>
                </div>
              </div>
              <ChatListPagination v-model:page="closedPage" v-model:page-size="closedPageSize" :total="recentInFolder.length" />
            </el-popover>
          </div>
          <p v-if="error" class="chat-workspace__error" role="alert">{{ error }} <el-button link @click="emit('retry')">重试</el-button></p>
          <div ref="sessionList" class="chat-workspace__list" @contextmenu="annotationMentionView && mentionSortMenu?.open($event)" @keydown.shift.f10="annotationMentionView && mentionSortMenu?.open($event)">
            <ChatSessionHistory v-if="(['all','mine'].includes(sessionScope) || appliedKeyword) && searchMode === 'sessions' && !annotationMentionView && !showMentions" :mine="sessionScope === 'mine'" :keyword="appliedKeyword" :revision="searchRevision" :active="active && pane === 'messages'" @open="emit('open', $event)" /><ChatMessageSearchResults v-else-if="searchMode === 'messages'" :keyword="appliedKeyword" :revision="searchRevision" @locate="emit('locate-mention', $event)" /><ChatMentionInbox v-else-if="showMentions" :keyword="appliedKeyword" :filters="mentionFilters" :active="pane === 'messages'" @total="filteredMentionTotal = $event" @locate="emit('locate-mention', $event)" />
            <template v-else>
            <div v-if="annotationMentionView && scopedMentionSenders.items.value.length" class="chat-workspace__mention-senders" role="group" aria-label="按当前分组提及人筛选">
              <button type="button" class="chat-mention-sender-pill" :class="{ 'is-active': !selectedMentionSender }" :aria-pressed="!selectedMentionSender" @click="selectMentionSender('')">全部提及人</button>
              <button v-for="person in visibleScopedMentionSenders" :key="person.userId" type="button" class="chat-mention-sender-pill" :class="{ 'is-active': selectedMentionSender === person.userId }" :aria-pressed="selectedMentionSender === person.userId" :title="`${person.name} · 共 ${person.count} 条${person.unreadCount ? `（未读 ${person.unreadCount} 条）` : ''}`" @click="selectMentionSender(person.userId)">
                <span class="chat-mention-sender-pill__name">{{ person.name }}</span>
                <b v-if="person.unreadCount" class="chat-mention-sender-pill__unread">{{ person.unreadCount > 99 ? '99+' : person.unreadCount }}</b>
                <small v-else class="chat-mention-sender-pill__count">{{ person.count }}</small>
              </button>
              <button v-if="scopedMentionSenders.items.value.length > 5" type="button" class="chat-mention-sender-pill chat-mention-sender-pill--more" @click="scopedSendersExpanded = !scopedSendersExpanded">{{ scopedSendersExpanded ? '收起' : `展开 (${scopedMentionSenders.items.value.length}人)` }}</button>
            </div>
            <el-empty v-if="!visibleSessions.length" :description="annotationMode === 'group' && annotationFiltersActive ? '没有符合筛选条件的标注会话' : annotationMentionView ? '当前筛选中没有提及消息的会话' : tab === 'unread' ? '没有未读消息' : '暂无会话'" :image-size="48" />
            <div v-for="session in pagedSessions" :key="session.key" class="chat-workspace__session" :class="{ 'is-active': session.opened && session.key === activeKey, 'is-pinned': session.pinned, 'has-unread-mention': !!session.mentionUnread }" role="button" tabindex="0" :title="[session.title, session.subtitle, session.projectType !== 'direct' && Number.isFinite(session.memberCount) ? `${session.memberCount}人` : ''].filter(Boolean).join(' · ')" @click="emit(session.opened ? 'select' : 'open', session)" @contextmenu="handleSessionContextMenu($event, session)" @keydown.shift.f10="handleSessionContextMenu($event, session)" @keydown.enter.self="emit(session.opened ? 'select' : 'open', session)" @keydown.space.self.prevent="emit(session.opened ? 'select' : 'open', session)">
              <span class="chat-workspace__session-left"><span class="chat-workspace__avatar" :class="`chat-workspace__avatar--${session.projectType}`" aria-hidden="true">{{ chatAvatarText(session.title) }}</span></span>
              <span class="chat-workspace__session-main">
                <span class="chat-workspace__session-title"><strong>{{ session.title || '未命名项目' }}</strong><el-icon v-if="session.starred" title="已收藏" class="chat-session-star"><StarFilled /></el-icon><time v-if="sessionDisplayTime(session)" :title="formatBusinessDateTime(sessionDisplayTime(session))">{{ chatDateLabel(sessionDisplayTime(session)) }}</time></span>
                <span v-if="['annotation', 'translation'].includes(session.projectType) && session.subtitle || (session.projectType !== 'direct' && Number.isFinite(session.memberCount))" class="chat-workspace__session-sub">
                  <ChatOrderIdentity :order-no="session.subtitle" :project-type="session.projectType" />
                  <span v-if="session.projectType !== 'direct' && Number.isFinite(session.memberCount)" class="chat-session-member-inline" :aria-label="`当前会话 ${session.memberCount} 人`">{{ typeLabel(session.projectType) }} · {{ session.memberCount }}人</span>
                </span>
                <span v-if="renamingDiscussion?.key === session.key" @click.stop @keydown.stop @mousedown.stop><ChatInlineNameEditor :initial-name="session.title" class="chat-compact-rename" label="会话名称" :saving="renameSaving" :error="renameError" @save="saveDiscussionName" @cancel="renamingDiscussion = null" /></span>
                <span class="chat-workspace__preview-row"><b v-if="personalUnread(session)" class="chat-mention-label chat-session-mention">[@我]</b><b v-if="session.mentionAllUnread" class="chat-mention-broadcast chat-session-mention">[@所有人]</b><small class="chat-session-preview"><mark v-if="!session.mentionUnread && session.lastMessage?.mentionsMe" class="chat-mention-preview" :class="{ 'chat-mention-broadcast': session.lastMessage.mentionAll }">{{ session.lastMessage.mentionAll ? '[@所有人]' : '[@我]' }}</mark><span v-if="session.lastMessage && isUrgentPreview(session.lastMessage.preview)" class="chat-preview-urgent">急</span>{{ session.lastMessage ? `${session.lastMessage.senderName}：${cleanPreviewText(session.lastMessage.preview)}` : session.projectType === 'discussion' && session.storageReady !== true ? '讨论暂未启用' : '暂无消息' }}</small><span v-if="session.mentionUnread" class="chat-session-unread" :aria-label="`${session.mentionUnread} 条未读提及`" title="未读提及">{{ session.mentionUnread > 99 ? '99+' : session.mentionUnread }}</span><span v-if="sessionUnreadSignal(session).ordinary" class="chat-session-unread-dot" :class="{ 'is-manual': session.manualUnread }" role="status" :aria-label="session.manualUnread ? '已标为未读' : '有普通未读消息'" :title="session.manualUnread ? '已标为未读' : '有普通未读消息'" /></span>
                <span v-if="session.variants.length > 1" class="chat-session-orders" @click.stop @keydown.stop>
                  <el-popover trigger="click" placement="right-start" :width="280">
                    <template #reference><el-button link size="small" :aria-label="`切换订单会话 ${session.subtitle}`">切换订单</el-button></template>
                    <div class="chat-session-order-options">
                      <el-button v-for="variant in session.variants" :key="variant.key" link :type="variant.key === activeKey ? 'primary' : ''" @click="emit(variant.opened ? 'select' : 'open', variant)">{{ variant.subtitle }}<span v-if="variant.mentionUnread">（{{ variant.mentionUnread }} 条未读提及）</span></el-button>
                    </div>
                  </el-popover>
                </span>
                <ProjectMentionPopover v-if="annotationMentionView && session.projectType === 'annotation'" :session="session" :model="projectMentions"
                  @browse="emit('browse-project-mentions', $event)" @select="emit('select-project-mention', $event)"
                  @more="emit('more-project-mentions')" @retry="emit('retry-project-mentions')" />
              </span>
              <el-icon v-if="session.pinned" title="已置顶" class="chat-session-pin"><Top /></el-icon>
              <span class="chat-workspace__session-controls" @click.stop @keydown.stop @mousedown.stop>
                <el-button link class="chat-session-more-btn" aria-label="会话操作" @click="openSessionMenu($event, session)">⋯</el-button>
              </span>
            </div>
            </template>
          </div>
          <ChatListPagination v-if="searchMode === 'sessions' && !showMentions && (annotationMentionView || (sessionScope === 'recent' && !appliedKeyword))" v-model:page="sessionPage" v-model:page-size="sessionPageSize" :total="visibleSessions.length" />
          </section>
          </Teleport>
        </template>
        <ChatContacts v-show="pane === 'contacts'" :active="pane === 'contacts'" @opened="contactOpened" />
        <ChatSettings v-if="pane === 'settings'" />
        <div v-if="!narrow" class="chat-workspace__split-handle" role="separator" tabindex="0" aria-orientation="vertical" aria-label="调整会话列表与聊天区域宽度" :aria-valuenow="sessionWidth" :aria-valuemin="220" :aria-valuemax="splitMaximum" title="左右拖动调整分区；双击恢复默认；左右方向键微调" @pointerdown.stop="emit('split-start', $event)" @keydown="emit('split-keydown', $event)" @dblclick.stop="emit('split-reset')" />
      </aside>
      <div ref="middleHost" v-show="middleList || panelDragging" class="chat-session-middle-host" :class="{ 'is-drop-target': panelDragging }" @dragover.prevent @drop.prevent="dropSessionPanel($event, 'middle')"><span v-if="panelDragging && !middleList">放在分组与聊天之间</span></div>
      <div class="chat-workspace__stage" @dragover="sessionPanelDragOver" @drop="dropSessionPanel($event, 'middle')"><template v-if="['summary','notifications','annotation-projects','translation-projects','interpretation-projects','consultations'].includes(pane)"><div v-if="!maximized||narrow" class="chat-workspace__pane-tabs" role="tablist" aria-label="沟通导航"><button v-for="item in panes" :key="item.key" :aria-label="item.label" @click="selectPane(item.key)" @contextmenu="openProjectMenu($event,item.key)" @keydown.shift.f10="openProjectMenu($event,item.key)">{{ item.label }}<span v-if="item.key === 'messages' && messageBadgeTotal" class="chat-pane-count">@{{ messageBadgeTotal > 99 ? '99+' : messageBadgeTotal }}</span></button></div><div class="chat-summary-content"><ChatRequestNotifications v-if="pane==='notifications'" :feed="notificationFeed" /><ChatAnnotationProjects v-else-if="pane==='annotation-projects'" :key="`annotation:${projectMine}`" :my-projects="projectMine" @navigate="emit('project-navigate')" @open-conversation="pane='messages'" /><ChatManagedProjects v-else-if="isProjectPane(pane)" :key="`${pane}:${projectMine}`" :module="projectModule(pane)" :my-projects="projectMine" /><DevelopmentIssuePanel v-else :open-issue-id="summaryIssueId" /></div></template><div v-else-if="!activeKey" class="chat-workspace__empty"><el-icon><ChatDotRound /></el-icon><strong>开始沟通</strong><span>选择会话，或从通讯录发起私聊</span></div></div>
      <el-popover v-model:visible="projectMenuVisible" :virtual-ref="projectMenuAnchor" virtual-triggering :trigger="[]" placement="right-start" :width="150" :z-index="100050"><el-button text @click="selectMyProjects">我的项目</el-button></el-popover>
      <el-popover v-model:visible="sessionMenuVisible" :virtual-ref="sessionMenuAnchor" virtual-triggering :trigger="[]" placement="bottom-start" :width="156" :z-index="sessionMenuZ" popper-class="chat-session-popover chat-session-context-popover">
        <div v-if="sessionMenuSession" class="chat-session-groups">
          <el-button link @click="runSessionPreference(sessionMenuSession, { pinned: !sessionMenuSession.pinned })">{{ sessionMenuSession.pinned ? '取消置顶' : '置顶' }}</el-button>
          <el-button link @click="runSessionPreference(sessionMenuSession, { starred: !sessionMenuSession.starred })">{{ sessionMenuSession.starred ? '取消收藏' : '收藏' }}</el-button>
          <el-button v-if="sessionMenuSession.projectType !== 'discussion' && categories.ready" link @click="openSessionCategory(sessionMenuSession)">设置分类</el-button>
          <el-button link @click="runSessionPreference(sessionMenuSession, hasSessionUnread(sessionMenuSession) ? { markRead: true } : { markUnread: true })">{{ hasSessionUnread(sessionMenuSession) ? '标为已读' : '标为未读' }}</el-button>
          <template v-if="sessionMenuSession.projectType === 'discussion'">
            <el-button v-if="categories.canManage && !sessionMenuSession.technicalProjectId" link :aria-label="`修改名称 ${sessionMenuSession.title}`" @click="runDiscussionRename(sessionMenuSession)">修改名称</el-button>
            <el-button v-if="sessionMenuSession.deletionProtected" link @click="runCloseSession(sessionMenuSession)">关闭会话</el-button>
            <el-button v-if="categories.canManage && !sessionMenuSession.deletionProtected && sessionMenuSession.subtitle !== '资源开拓讨论'" link type="danger" @click="runDeleteDiscussion(sessionMenuSession)">删除会话</el-button>
          </template>
        </div>
      </el-popover>
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
import ChatAnnotationFilters from './ChatAnnotationFilters.vue'
import { chatRequest } from '@/api/projectChat'
import ChatInlineNameEditor from './ChatInlineNameEditor.vue'
import { canStartChatNameEditing } from '@/composables/useChatNameEditing'
import ChatMentionSortMenu from './ChatMentionSortMenu.vue'
import { compareMentionSessions, latestMentionAt } from '@/utils/chatMentionSort'
import { groupSessionList, sessionListKey, mentionUnreadCount, sessionUnreadSignal, firstUnreadMentionSession, compareSessionActivity } from '@/utils/chatSessionList'

import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Bell, ArrowDown, ArrowLeft, ArrowRight, ChatDotRound, Collection, Headset, Filter, Message, MoreFilled, Search, Setting, Star, StarFilled, Top, User, EditPen, Microphone, Phone } from '@element-plus/icons-vue'
import { chatOverlayZIndex } from '@/utils/chatOverlay'
const DevelopmentIssuePanel=defineAsyncComponent(()=>import('@/views/resource/components/DevelopmentIssuePanel.vue'))
import ChatSettings from './ChatSettings.vue'
import { hasPermission } from '@/utils/permission'
import AnnotationChatInbox from './AnnotationChatInbox.vue'
const ChatAnnotationProjects = defineAsyncComponent(() => import('./ChatAnnotationProjects.vue'))
const ChatManagedProjects = defineAsyncComponent(() => import('./ChatManagedProjects.vue'))
import ChatWindowControls from './ChatWindowControls.vue'
import ChatRequestNotifications from './ChatRequestNotifications.vue'
import { useChatRequestNotifications } from '@/composables/useChatRequestNotifications'
const notificationFeed = useChatRequestNotifications()
import ChatConversationParticipants from './ChatConversationParticipants.vue'
import { chatAvatarText, chatDateLabel } from '@/utils/chatLayout'
import { formatBusinessDateTime } from '@/utils/dateTime'
import ChatContacts from './ChatContacts.vue'
import ChatMentionInbox from './ChatMentionInbox.vue'
import ChatMessageSearchResults from './ChatMessageSearchResults.vue'
import ChatSessionHistory from './ChatSessionHistory.vue'
import ChatListPagination from './ChatListPagination.vue'
import ProjectMentionPopover from './ProjectMentionPopover.vue'
import ChatConversationMore from './ChatConversationMore.vue'
import ChatPinIcon from './ChatPinIcon.vue'
import ChatSessionFolderTree from './ChatSessionFolderTree.vue'
import ChatAnnotationProjectPicker from './ChatAnnotationProjectPicker.vue'
import { normalizeAnnotationStatus } from '@/utils/annotationStatus'
import { annotationFolderId, annotationStatusGroupId, resourceFolderId, resourceDiscussionIds, sessionFolderNodes, sessionMatchesFolder } from '@/utils/chatSessionFolders'
import { useChatMentionSenders } from '@/composables/useChatMentionSenders'
import ChatSessionCategoryAssignment from './ChatSessionCategoryAssignment.vue'
import { categoryKey, useChatSessionCategories } from '@/composables/useChatSessionCategories'

const props = defineProps({
  annotationFilters: { type: Object, default: () => ({ mine: false, statuses: [] }) },
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
  splitMaximum: { type: Number, default: 600 },
  title: { type: String, default: '沟通' },
  subtitle: { type: String, default: '' },
  projectType: { type: String, default: '' },
  metaLoading: { type: Boolean, default: false },
  dragging: { type: Boolean, default: false },
})
const emit = defineEmits([
  'annotation-filters',
  'split-start', 'split-keydown', 'split-reset',
  'remove-closed-history', 'clear-closed-history', 'restore-closed', 'browse-project-mentions', 'select-project-mention', 'more-project-mentions', 'retry-project-mentions',
  'session-panel-dragging', 'session-panel-width', 'project-navigate', 'normal-size', 'context-empty', 'duplicate-window', 'open-multiple', 'pane-change', 'preference', 'categories-changed', 'select', 'open', 'locate-mention', 'close', 'close-active', 'exit-workspace', 'minimize', 'cycle-size', 'toggle-maximize', 'toggle-layout',
  'open-search', 'toggle-sidebar', 'header-mousedown', 'header-dblclick', 'retry', 'pin', 'resize', 'fullscreen', 'contact-opened',
])

const panes = [{ key: 'messages', label: '消息', icon: ChatDotRound }, { key: 'contacts', label: '通讯录', icon: User }, { key: 'summary', label: '总结', icon: Collection }, { key: 'notifications', label: '通知', icon: Bell }, ...(hasPermission('projects:read') ? [{ key: 'annotation-projects', label: '标注项目', icon: Headset },{key:'translation-projects',label:'笔译项目',icon:EditPen},{key:'interpretation-projects',label:'口译项目',icon:Microphone}] : []), ...(hasPermission('consultations:read')?[{key:'consultations',label:'新咨询管理',shortLabel:'新咨询',icon:Phone}]:[]), { key: 'settings', label: '设置', icon: Setting }]
const isUrgentPreview = text => /^\s*\*\*急\*\*/.test(String(text || ''))
const cleanPreviewText = text => screenshotPreview(String(text || '').replace(/^\s*\*\*急\*\*\s*/, ''))
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
const typeLabel = type => type === 'discussion' ? '讨论' : type === 'direct' ? '私聊' : type === 'annotation' ? '标注' : '笔译'
function contactOpened() {
  annotationMode.value = 'direct'
  tab.value = 'direct'
  selectedFolder.value = ''
  keyword.value = ''; applyKeyword()
  pane.value = 'messages'
  emit('contact-opened')
}
const groups = [{ key: 'all', label: '消息' }, { key: 'pinned', label: '置顶' }, { key: 'unread', label: '未读' }, { key: 'mention', label: '@我' }, { key: 'direct', label: '私聊' }, { key: 'starred', label: '特别关注' }, { key: 'project', label: '项目群' }, { key: 'annotation', label: '标注项目群' }, { key: 'translation', label: '笔译项目群' }, { key: 'creator', label: '我创建的' }]
const { categories } = useChatSessionCategories()
const sessionScope = ref('recent')
const middleHost = ref(null)
const panelDragging = ref(false)
watch(panelDragging, value => emit('session-panel-dragging', value))
const panelStorageKey = `xinshi.chatSessionPanel.${localStorage.getItem('user_id') || 'anonymous'}`
const panelPlacement = ref('bottom')
try { if (localStorage.getItem(panelStorageKey) === 'middle') panelPlacement.value = 'middle' } catch { /* 使用默认位置。 */ }
const middleList = computed(() => panelPlacement.value === 'middle' && !props.narrow && !props.mobile && pane.value === 'messages')
watch(middleList, value => emit('session-panel-width', value ? 300 : 0), { immediate: true })
function setPanelPlacement(value) {
  panelPlacement.value = value; panelDragging.value = false
  try { localStorage.setItem(panelStorageKey, value) } catch { /* 本次布局仍生效。 */ }
}
function sessionPanelDragOver(event) {
  if (panelDragging.value) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' }
}
function startSessionPanelDrag(event) {
  event.stopPropagation()
  event.dataTransfer.setData('application/x-xinshi-session-panel', 'move')
  event.dataTransfer.effectAllowed = 'move'
  panelDragging.value = true
}
function dropSessionPanel(event, placement) {
  if (!panelDragging.value || event.dataTransfer.getData('application/x-xinshi-session-panel') !== 'move') return
  event.stopPropagation(); setPanelPlacement(placement)
}
function setSessionScope(scope) {
  sessionScope.value = scope
  if (scope === 'all' || scope === 'mine') { annotationMode.value = 'group'; tab.value = 'all'; selectedFolder.value = ''; nextTick(() => { sessionScope.value = scope }) }
}
const sessionPage=ref(1),sessionPageSize=ref(20),closedPage=ref(1),closedPageSize=ref(20)
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
  const items = [...props.recentClosed]
  recentClosedVisible.value = false
  // 从较早的记录开始打开，使最新关闭的会话最后成为当前会话。
  for (const item of items.reverse()) emit('restore-closed', item)
}
const recentInFolder = computed(() => props.recentClosed.filter(item => annotationMode.value === 'direct'
  ? item.projectType === 'direct' : item.projectType !== 'direct' && sessionMatchesFolder(item, selectedFolder.value, folderNodes.value)))
const pagedRecentClosed=computed(()=>recentInFolder.value.slice((closedPage.value-1)*closedPageSize.value,closedPage.value*closedPageSize.value))
async function clearRecentHistory(){
  try{await ElMessageBox.confirm('清空全部最近关闭记录？会话和聊天记录仍然保留。','清空最近关闭',{confirmButtonText:'清空',cancelButtonText:'取消',type:'warning',zIndex:recentMenuZ.value+1})}catch{return}
  emit('clear-closed-history');closedPage.value=1
}
const activeSession = computed(() => {
  if (!props.activeKey) return null
  return props.sessions.find(row => row.key === props.activeKey)
    || props.searchSessions.find(row => row.key === props.activeKey)
    || (props.projectId && props.projectType ? { key: props.activeKey, projectId: props.projectId, projectType: props.projectType, title: props.title, subtitle: props.subtitle, pinned: false, starred: false } : null)
})
const sessionMenuVisible = ref(false), sessionMenuAnchor = ref(null), sessionMenuSession = ref(null), sessionMenuZ = ref(2120)
function closeSessionMenu() { sessionMenuVisible.value = false }
function onSessionMenuOutside(event) {
  if (!sessionMenuVisible.value) return
  if (event.target?.closest?.('.chat-session-context-popover, .chat-session-more-btn')) return
  sessionMenuVisible.value = false
}
function onSessionMenuEscape(event) {
  if (event.key === 'Escape' && sessionMenuVisible.value) sessionMenuVisible.value = false
}
function openSessionMenu(event, session) {
  event.preventDefault(); event.stopPropagation()
  if (sessionMenuVisible.value && sessionMenuSession.value?.key === session.key && event.type === 'click') {
    sessionMenuVisible.value = false
    return
  }
  const target = event.currentTarget
  sessionMenuSession.value = session
  sessionMenuZ.value = chatOverlayZIndex(target)
  sessionMenuAnchor.value = event.type === 'contextmenu'
    ? { getBoundingClientRect: () => DOMRect.fromRect({ x: event.clientX, y: event.clientY, width: 0, height: 0 }) }
    : target
  sessionMenuVisible.value = true
}
function handleSessionContextMenu(event, session) {
  if (annotationMentionView.value) return
  openSessionMenu(event, session)
}
function runSessionPreference(session, data) { closeSessionMenu(); emit('preference', { session, data }) }
function openSessionCategory(session) { closeSessionMenu(); categoryAssignment.value?.open(session) }
function runDiscussionRename(session) { closeSessionMenu(); startDiscussionRename(session) }
function runCloseSession(session) { closeSessionMenu(); emit('close', session) }
function runDeleteDiscussion(session) { closeSessionMenu(); deleteDiscussion(session) }
onMounted(() => {
  document.addEventListener('pointerdown', onSessionMenuOutside, true)
  document.addEventListener('keydown', onSessionMenuEscape)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onSessionMenuOutside, true)
  document.removeEventListener('keydown', onSessionMenuEscape)
})
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
  if (!row || row.deletionProtected || session.deletionProtected) return
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
const tab = ref('all')
watch(() => [categories.loaded, categories.ready, categories.items.map(row => `${row.id}:${row.active}`).join(',')], ([loaded, ready]) => {
  if (loaded && tab.value.startsWith('category:') && (!ready || !categories.items.some(row => row.active && categoryKey(row.id) === tab.value))) tab.value = 'all'
})
const groupsVisible = ref(false), groupPicker = ref(null)
const folderStorageKey = `xinshi.chatFolder.${localStorage.getItem('user_id') || 'anonymous'}`
let savedFolder = tab.value === 'annotation' ? annotationFolderId : ''
try { savedFolder = localStorage.getItem(folderStorageKey) ?? savedFolder } catch { /* 使用默认目录。 */ }
if (resourceDiscussionIds.includes(savedFolder)) savedFolder = resourceFolderId
const selectedFolder = ref(savedFolder)
const folderTreeRef=ref()
const folderNodes = computed(() => sessionFolderNodes(categories.items, { technicalAccess: categories.technicalAccess }))
const searchMode = ref('sessions'), searchRevision = ref(0)
const searchPlaceholder = computed(() => searchMode.value === 'messages' ? '关键词' : '名称/单号')
watch(selectedFolder, value => { try { localStorage.setItem(folderStorageKey, value) } catch { /* 本次选择仍生效。 */ } })
watch(() => [categories.loaded, ...folderNodes.value.map(row => row.id)], ([loaded]) => { if (loaded && selectedFolder.value && !folderNodes.value.some(row => row.id === selectedFolder.value)) selectedFolder.value = categories.items.find(row => row.id === selectedFolder.value)?.parentKey === resourceFolderId ? resourceFolderId : '' }, { immediate: true })
function selectFolder(id) {
  pendingContextFolder = ''
  selectedMentionSender.value = ''
  scopedSendersExpanded.value = false
  if (annotationMode.value === 'mention-all') annotationMode.value = 'group'
  tab.value = 'all'
  selectedFolder.value = id
}
function openMentionInbox(mode) {
  tab.value = 'all'
  selectedFolder.value = ''
  selectedMentionSender.value = ''
  scopedSendersExpanded.value = false
  searchMode.value = 'sessions'
  annotationMode.value = mode
}
function openMentionSender(userId, fromFilter = false) {
  pendingContextFolder = ''
  tab.value = fromFilter ? 'mention' : 'all'
  selectedFolder.value = ''
  searchMode.value = 'sessions'
  annotationMode.value = 'mention'
  selectedMentionSender.value = String(userId || '')
  if (fromFilter) groupPicker.value?.minimize()
}
function selectMentionSender(userId) {
  selectedMentionSender.value = String(userId || '')
}
const personalUnread = session => (Number(session.mentionUnread) || 0) > (Number(session.mentionAllUnread) || 0)
function openFolderConversation(session) { pendingContextFolder = ''; pane.value = 'messages'; annotationMode.value = 'group'; tab.value = 'all'; selectedMentionSender.value = ''; selectedFolder.value = session.projectId; emit('open', session) }
const mentionSort = ref('time_desc'), mentionSortMenu = ref(null)
const annotationMode = ref('group')
const selectedMentionSender = ref('')
const filterMentionExpanded = ref(false)
const scopedSendersExpanded = ref(false)
const globalMentionSenders = useChatMentionSenders(computed(() => props.active && pane.value === 'messages'), computed(() => ({ mentionKind: 'personal' })))
const mentionFolderParams = computed(() => {
  const id = selectedFolder.value
  if (!id) return {}
  if (id === annotationFolderId || id === annotationStatusGroupId) return { projectType: 'annotation' }
  if (id.startsWith('status:')) return { projectType: 'annotation', projectStatus: id.slice(7) }
  if (id === resourceFolderId) return { projectType: 'discussion' }
  const node = folderNodes.value.find(row => row.id === id)
  if (!node) return {}
  if (node.ruleKey === 'translation') return { projectType: 'translation' }
  if (node.isConversation) return { projectType: 'discussion', projectId: node.id }
  return {}
})
const hasMentionFolderScope = computed(() => Object.keys(mentionFolderParams.value).length > 0)
const scopedMentionSenders = useChatMentionSenders(
  computed(() => props.active && pane.value === 'messages' && annotationMode.value === 'mention' && !!selectedFolder.value && !selectedMentionSender.value && hasMentionFolderScope.value),
  computed(() => ({ mentionKind: 'personal', ...mentionFolderParams.value })),
)
const visibleScopedMentionSenders = computed(() => scopedSendersExpanded.value ? scopedMentionSenders.items.value : scopedMentionSenders.items.value.slice(0, 5))
const mentionFilters = computed(() => ({
  sort: mentionSort.value,
  mentionKind: annotationMode.value === 'mention-all' ? 'all' : 'personal',
  senderId: selectedMentionSender.value || undefined,
  ...(annotationMode.value === 'mention' ? mentionFolderParams.value : {}),
}))
const showMentions = computed(() => annotationMode.value === 'mention-all' || (annotationMode.value === 'mention' && (!selectedFolder.value || !!selectedMentionSender.value)))
const annotationMentionView = computed(() => annotationMode.value === 'mention')
const filteredMentionTotal = ref(0)
watch(annotationMode, value => {
  if (value !== 'mention' && value !== 'mention-all') selectedMentionSender.value = ''
})
watch(tab, (key, previous) => {
  if (key === 'direct') annotationMode.value = 'direct'
  else if (key === 'mention') { annotationMode.value = 'mention'; selectedFolder.value = '' }
  else if (previous === 'direct' || previous === 'mention') annotationMode.value = 'group'
})

const hasSessionUnread = session => !!session && (Number(session.unread) > 0 || Number(session.mentionUnread) > 0 || !!session.manualUnread)
function inGroup(session, key) {
  if (key.startsWith('category:')) return !!session.categoryIds?.includes(key.slice('category:'.length))
  if (key === 'all') return true
  if (key === 'unread') return hasSessionUnread(session)
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
watch(pane, (current, previous) => {
  if (previous === 'notifications') void notificationFeed.reset()
  if (previous === 'messages') {
    groupsVisible.value = false
    filterMentionExpanded.value = false
    selectedMentionSender.value = ''
    tab.value = 'all'
    keyword.value = ''
    searchMode.value = 'sessions'
    applyKeyword()
  }
})

const annotationFiltersActive = computed(() => props.annotationFilters.mine || props.annotationFilters.statuses.length > 0)
watch(() => props.annotationFilters, () => {
  pane.value = 'messages'
  annotationMode.value = 'group'
  tab.value = 'all'
  selectedFolder.value = ''
  searchMode.value = 'sessions'
  keyword.value = ''
  applyKeyword()
  nextTick(() => { if (sessionList.value) sessionList.value.scrollTop = 0 })
})

watch([annotationMode, selectedFolder, tab], () => { sessionScope.value = 'recent' })
const sessionDisplayTime = session => annotationMentionView.value ? latestMentionAt(session) : session.lastMessage?.createdAt
const visibleSessions = computed(() => groupSessionList((appliedKeyword.value ? [...new Map([...props.searchSessions,...props.sessions].map(row=>[row.key,row])).values()] : (annotationMentionView.value || selectedFolder.value) ? allMentionSessions.value : props.sessions).filter((session) => {
  const directMode = annotationMode.value === 'direct'
  if (annotationMode.value === 'group' && annotationFiltersActive.value) {
    const { mine, statuses } = props.annotationFilters
    if (session.projectType !== 'annotation' || (mine && !session.isProjectManager) ||
      (statuses.length && !statuses.includes(normalizeAnnotationStatus(session.projectStatus)))) return false
  }
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
 if(!external&&(showMentions.value || (annotationMode.value === 'group' && annotationFiltersActive.value)))return
 const target=activeConversationFolder(session,folderNodes.value,selectedFolder.value)
 if(external){pendingContextFolder='';pane.value='messages';keyword.value='';applyKeyword()}
 if(context.projectType==='direct'){annotationMode.value='direct';tab.value='direct';selectedFolder.value=''}
 else{if(annotationMode.value==='direct'||selectedFolder.value&&target!==selectedFolder.value||external&&!showMentions.value){annotationMode.value='group';tab.value='all'}selectedFolder.value=target}
 nextTick(()=>{if(external && selectedFolder.value===target)folderTreeRef.value?.reveal(target);const index=visibleSessions.value.findIndex(row=>row.key===props.activeKey||row.variants?.some(item=>item.key===props.activeKey));if(index>=0)sessionPage.value=Math.floor(index/sessionPageSize.value)+1;nextTick(()=>{const element=sessionList.value?.querySelector('.chat-workspace__session.is-active');element?.scrollIntoView({block:'nearest'})})})
}
const pagedSessions=computed(()=>visibleSessions.value.slice((sessionPage.value-1)*sessionPageSize.value,sessionPage.value*sessionPageSize.value))
watch(()=>recentInFolder.value.length,total=>{closedPage.value=Math.min(closedPage.value,Math.max(1,Math.ceil(total/closedPageSize.value)))})
watch([selectedFolder,annotationMode,tab,appliedKeyword],()=>{sessionPage.value=1;closedPage.value=1})
watch(()=>visibleSessions.value.length,total=>{sessionPage.value=Math.min(sessionPage.value,Math.max(1,Math.ceil(total/sessionPageSize.value)))})
function cancelPendingContext(){pendingContextFolder=''}
onMounted(()=>window.addEventListener('chat-conversation-opening',cancelPendingContext))
onBeforeUnmount(()=>window.removeEventListener('chat-conversation-opening',cancelPendingContext))
function activateFromOutside(event){const context=event.detail||{};nextTick(()=>{if(props.projectId===String(context.projectId)&&props.projectType===context.projectType)syncActiveConversation(context,true)})}
watch(()=>[props.activeKey,props.projectId,props.projectType],()=>{if(props.activeKey)syncActiveConversation({projectId:props.projectId,projectType:props.projectType})},{flush:'post'})
onMounted(()=>window.addEventListener('chat-conversation-activated',activateFromOutside))
onBeforeUnmount(()=>window.removeEventListener('chat-conversation-activated',activateFromOutside))
function showAnnotation() { pane.value = 'messages'; annotationMode.value = 'group'; selectFolder(annotationFolderId) }
function showSummary(event){pane.value='summary';summaryIssueId.value='';nextTick(()=>{summaryIssueId.value=event.detail?.issueId||''})}
let pendingContextFolder = ''
function openContextFirst() {
  if (!pendingContextFolder) return
  if (props.activeKey) { pendingContextFolder = ''; return }
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
<style src="./chatTokens.css" />

<style scoped>
/* ===== 框架与标题栏（栅格结构见 chatHeader.css，窗口按钮见 ChatWindowControls.vue） ===== */
.chat-workspace__frame{position:relative;display:flex;width:100%;height:100%;min-height:0;flex-direction:column;color:var(--chat-text)}
.chat-workspace__header{border-bottom:1px solid var(--chat-border);cursor:grab;user-select:none}
.chat-workspace__header--dragging{cursor:grabbing}
.chat-workspace__header--pinned{cursor:default}
.chat-workspace__heading strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:600}
.chat-workspace__subtitle{font-size:12px;color:var(--chat-text-faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* ===== 主体与侧栏 ===== */
.chat-workspace__body{display:flex;min-height:0;flex:1}
.chat-workspace__sessions{display:flex;min-width:0;min-height:0;flex:none;flex-direction:column;overflow:hidden;box-sizing:border-box;border-right:1px solid var(--chat-border);background:var(--chat-sidebar-bg)}
.chat-workspace__brand{display:flex;align-items:center;justify-content:space-between;gap:8px;height:46px;flex:none;padding:0 12px 0 14px;box-sizing:border-box;color:var(--color-text-primary)}
.chat-workspace__brand-title{display:flex;align-items:baseline;gap:6px;min-width:0}
.chat-workspace__brand small{font-size:11px;color:var(--chat-text-faint)}
.chat-workspace__split-reset{flex:none;border:0;border-radius:5px;background:transparent;padding:3px 6px;font:inherit;font-size:11px;color:var(--chat-text-faint);cursor:pointer;transition:background-color .14s ease,color .14s ease}
.chat-workspace__split-reset:hover{background:var(--chat-hover-bg);color:var(--chat-text)}
.chat-workspace__pane-tabs{display:flex;padding:8px 10px;gap:4px;flex:none;overflow-x:auto;scrollbar-width:none}
.chat-workspace__pane-tabs::-webkit-scrollbar{display:none}
.chat-workspace__pane-tabs button{display:flex;flex:1 0 auto;align-items:center;justify-content:center;gap:4px;min-width:0;height:var(--chat-control-h);border:0;border-radius:var(--chat-radius);padding:0 10px;font:inherit;font-size:12px;color:var(--chat-text-muted);background:transparent;cursor:pointer;white-space:nowrap}
.chat-workspace__pane-tabs button:hover{background:var(--chat-hover-bg)}
.chat-workspace__pane-tabs .is-active{background:var(--chat-active-bg);color:var(--color-primary-hover);font-weight:600}
.chat-pane-count{min-width:16px;padding:0 5px;border-radius:8px;background:#ef4444;color:#fff;font-size:10px;line-height:16px}

/* 搜索与分组筛选：一体化 32px 搜索框 + 等高 32×32px 方形筛选按钮 */
.chat-workspace__session-tools{display:flex;align-items:center;gap:6px;padding:2px 12px 8px;flex:none;min-width:0}
.chat-workspace__search{flex:1;min-width:0}
.chat-workspace__search :deep(.el-input-group){display:flex;align-items:center;box-sizing:border-box;width:100%;height:32px;border:1px solid #dce4ee;border-radius:7px;background:#fff;overflow:hidden;transition:border-color .14s ease,box-shadow .14s ease}
.chat-workspace__search :deep(.el-input-group:hover){border-color:#c6d4e5}
.chat-workspace__search :deep(.el-input-group:focus-within){border-color:var(--color-primary,#334155);box-shadow:0 0 0 2px rgba(51,65,85,.08)}
.chat-workspace__search :deep(.el-input-group__prepend){display:flex;align-items:center;flex:none;width:auto;height:30px;padding:0;border:0;border-right:1px solid #e2e8f0;border-radius:0;background:#f8fafc;box-shadow:none!important}
.chat-workspace__search :deep(.el-input-group__prepend .el-select){margin:0!important}
.chat-workspace__search :deep(.el-input__wrapper){flex:1;min-width:0;height:30px;min-height:30px;padding:0 6px 0 7px;border:0;border-radius:0;background:transparent;box-shadow:none!important;font-size:12px}
.chat-workspace__search :deep(.el-input__inner::placeholder){color:#94a3b8;font-size:12px}
.chat-search-mode{width:66px;margin:0}
.chat-search-mode :deep(.el-select__wrapper){width:100%;box-sizing:border-box;height:30px;min-height:30px;padding:0 5px 0 8px;gap:2px;border:0;border-radius:0;background:transparent;box-shadow:none!important;font-size:12px;color:#334155}
.chat-search-submit{display:inline-flex;align-items:center;justify-content:center;padding:0;border:0;background:transparent;color:var(--chat-text-faint);cursor:pointer}
.chat-search-submit:hover{color:var(--color-primary)}
.chat-workspace__tabs{flex:none;min-width:0}
.chat-workspace__tabs :deep(.chat-workspace__filter){position:relative;display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;width:32px;min-width:32px;height:32px;min-height:32px;margin:0;padding:0;border:1px solid #dce4ee;border-radius:7px;background:#fff;color:#475569;font-size:14px;transition:background-color .14s ease,border-color .14s ease,color .14s ease}
.chat-workspace__tabs :deep(.chat-workspace__filter:hover){border-color:#c6d4e5;background:#eef3f8;color:#1e293b}
.chat-workspace__tabs :deep(.chat-workspace__filter.is-active){border-color:var(--color-primary,#334155);background:#e7eef6;color:#1e293b}
.chat-workspace__tabs :deep(.chat-workspace__filter-dot){display:block;position:absolute;top:4px;right:4px;width:6px;height:6px;margin:0!important;padding:0!important;border-radius:50%;background:var(--color-primary,#334155);pointer-events:none}

/* 群聊 / 私聊 / @我 / @所有人：干净分段控件 */
.chat-workspace__annotation-filters{flex:none;padding:0 12px 10px;border-bottom:1px solid var(--chat-border)}
.chat-workspace__annotation-mode{display:flex;gap:2px;padding:3px;border-radius:8px;background:#e9eef5}
.chat-workspace__annotation-mode button{flex:1;min-width:0;height:26px;border:0;border-radius:6px;background:transparent;color:var(--chat-text-muted);padding:0 4px;font:inherit;font-size:12px;white-space:nowrap;cursor:pointer;transition:background-color .14s ease,color .14s ease,box-shadow .14s ease}
.chat-workspace__annotation-mode button:hover{color:var(--color-primary-hover)}
.chat-workspace__annotation-mode button.is-active{background:#fff;color:var(--color-primary-hover);font-weight:600;box-shadow:0 1px 2px rgba(15,23,42,.08)}
.chat-workspace__annotation-mode button.has-unread-mention{color:#b91c1c}
.chat-workspace__annotation-mode button.has-unread-mention.is-active{box-shadow:0 1px 2px rgba(185,28,28,.16),inset 0 0 0 1px rgba(185,28,28,.3)}
.chat-workspace__annotation-mode button:focus-visible{outline:2px solid var(--color-primary);outline-offset:1px}
.chat-session-mention-history{color:#64748b;font-size:11px}

.chat-workspace__recent-closed{display:flex;align-items:center;gap:4px;flex:none;padding:4px 10px;border-bottom:1px solid var(--chat-border)}
.chat-recent-closed{max-height:min(440px,calc(100vh - 120px));overflow-y:auto}
.chat-recent-closed__tools{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid var(--chat-divider);font-size:12px}
.chat-recent-closed__item{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--chat-divider)}
.chat-recent-closed__item>span{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
.chat-recent-closed__item strong{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-recent-closed__item small,.chat-discussion-protected{color:var(--chat-text-faint);font-size:11px}
.chat-session-orders .el-button{max-width:100%;font-size:11px;white-space:normal;text-align:left}
.chat-session-order-options{display:flex;flex-direction:column;align-items:flex-start;gap:10px;max-height:320px;overflow-y:auto}
.chat-session-order-options .el-button{margin:0;white-space:normal;text-align:left}
.chat-session-groups{display:flex;flex-direction:column;align-items:stretch;max-height:400px;overflow:auto}
.chat-session-groups .el-button{margin:0;justify-content:flex-start;padding:7px 8px}
.chat-session-group-row{display:flex;align-items:center;justify-content:space-between;gap:4px}
.chat-session-group-row .el-button{flex:1;min-width:0}
.chat-session-group-toggle{display:inline-flex;align-items:center;justify-content:center;flex:none;width:24px;height:24px;border:0;border-radius:4px;background:transparent;color:#64748b;cursor:pointer;transition:background-color .12s ease,color .12s ease}
.chat-session-group-toggle:hover{background:#eef3f8;color:#1e293b}
.chat-session-group-sub{display:flex;flex-direction:column;align-items:stretch;margin:2px 0 4px 12px;padding-left:10px;border-left:1px solid #dce4ee}
.chat-session-group-sub .el-button{padding:5px 8px;font-size:12px}
.chat-session-group-unread{display:inline-flex;align-items:center;justify-content:center;min-width:16px;height:16px;margin-left:6px;padding:0 4px;border-radius:8px;background:#dc2626;color:#fff;font-size:10px;font-weight:600;line-height:1}
.chat-workspace__mention-senders{display:flex;flex-wrap:wrap;gap:5px;padding:4px 4px 8px;margin-bottom:6px;border-bottom:1px solid #e9eef5}
.chat-mention-sender-pill{display:inline-flex;align-items:center;gap:4px;max-width:100%;height:24px;padding:0 8px;border:1px solid #dce4ee;border-radius:12px;background:#fff;color:#475569;font:inherit;font-size:11.5px;line-height:1;cursor:pointer;transition:background-color .12s ease,border-color .12s ease,color .12s ease}
.chat-mention-sender-pill:hover{background:#eef3f8;border-color:#cbd5e1;color:#1e293b}
.chat-mention-sender-pill.is-active{background:#334155;border-color:#334155;color:#fff;font-weight:500}
.chat-mention-sender-pill__name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:96px}
.chat-mention-sender-pill__count{font-size:10.5px;color:#94a3b8;font-variant-numeric:tabular-nums}
.chat-mention-sender-pill.is-active .chat-mention-sender-pill__count{color:rgba(255,255,255,.78)}
.chat-mention-sender-pill__unread{display:inline-flex;align-items:center;justify-content:center;min-width:15px;height:15px;padding:0 4px;border-radius:8px;background:#dc2626;color:#fff;font-size:10px;font-weight:600;line-height:1}
.chat-mention-sender-pill--more{border-style:dashed;background:transparent;color:#64748b}
.chat-workspace__error{padding:8px 12px;color:#b91c1c;font-size:12px}

/* 会话列表卡片：铺满右侧空间，悬停时操作按钮平滑覆盖右上角时间，无斑马纹、无右侧空列 */
.chat-workspace__list{flex:1;min-height:0;overflow-y:auto;padding:6px 8px 10px}
.chat-workspace__session{position:relative;display:flex;box-sizing:border-box;width:100%;min-height:64px;padding:9px 10px;align-items:center;gap:10px;border-radius:8px;color:var(--chat-text);cursor:pointer;font:inherit;transition:background-color .14s ease,border-color .14s ease}
.chat-workspace__session.is-pinned{background:#f1f5f9}
.chat-workspace__session:hover{background:var(--chat-hover-bg)}
.chat-workspace__session.is-active{background:var(--chat-active-bg)}
.chat-workspace__session:focus-visible{outline:2px solid var(--color-primary);outline-offset:-2px}
.chat-session-mention{flex:none;font-size:11px;white-space:nowrap}
.chat-mention-broadcast{color:#9a3412;background:#ffedd5;border-radius:3px;padding:0 3px}
.chat-workspace__session.has-unread-mention .chat-workspace__session-title strong{color:#b91c1c}
.chat-workspace__session-left{display:flex;flex:none;align-items:center;justify-content:center;width:36px}
.chat-workspace__avatar{position:relative;display:grid;flex:none;place-items:center;width:36px;height:36px;border-radius:10px;background:#e4ebf4;color:#3b526b;font-size:14px;font-weight:600}
.chat-workspace__avatar--annotation{background:#e2f0ea;color:#2b6b56}
.chat-workspace__avatar--direct{border-radius:50%;background:#ebe6f5;color:#62508a}
.chat-workspace__session-main{display:flex;min-width:0;flex:1;flex-direction:column;gap:3px}
.chat-workspace__session-title,.chat-workspace__preview-row{display:flex;align-items:center;gap:6px;min-width:0}
.chat-workspace__session-title strong{font-size:13px;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--color-text-primary)}
.chat-workspace__session-title time{flex:none;font-size:11px;color:var(--chat-text-faint);pointer-events:none;font-variant-numeric:tabular-nums;transition:opacity .12s ease}
.chat-workspace__session-sub{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;font-size:11px;color:var(--chat-text-faint);line-height:1.35}
.chat-workspace__session-sub :deep(.chat-order-identity){flex:1 1 auto;min-width:0}
.chat-workspace__session-sub :deep(.chat-order-identity__details){flex-wrap:nowrap;overflow:hidden;white-space:nowrap}
.chat-workspace__session-sub :deep(.chat-order-identity__number){overflow:hidden;text-overflow:ellipsis;white-space:nowrap;overflow-wrap:normal}
.chat-session-member-inline{flex:none;font-size:11px;color:var(--chat-text-faint);white-space:nowrap}
.chat-session-star{color:#d97706;font-size:12px;flex:none}
.chat-session-preview{display:block;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:var(--chat-text-muted)}
.chat-preview-urgent{display:inline-flex;align-items:center;justify-content:center;margin-right:4px;padding:0 4px;height:15px;border-radius:3px;background:#fee2e2;color:#dc2626;font-size:10px;font-weight:600;line-height:15px;vertical-align:1px}
.chat-session-unread{flex:none;min-width:16px;box-sizing:border-box;padding:1px 5px;border-radius:10px;background:#ef4444;color:#fff;font-size:10px;text-align:center}
.chat-session-unread-dot{display:inline-block;flex:none;width:6px;height:6px;border-radius:50%;background:var(--chat-text-faint);margin:0 2px}
.chat-session-unread-dot.is-manual{width:8px;height:8px;background:#ef4444}
.chat-mention-label{color:#dc2626}
.chat-mention-preview{margin-right:4px;padding:0 3px;border-radius:3px;background:#fef3c7;color:#92400e}
.chat-session-pin{position:absolute;top:4px;left:4px;font-size:11px;color:var(--color-primary)}
.chat-workspace__quick-action{color:var(--chat-text-muted)}
.chat-workspace__quick-action.is-active{color:var(--color-primary)}
.chat-workspace__quick-action.is-starred{color:#d97706}
.chat-workspace__quick-action.is-unread{color:#ef4444}
.chat-workspace__session-controls{position:absolute;top:8px;right:8px;z-index:2;display:flex;align-items:center;justify-content:flex-end;opacity:0;pointer-events:none;transition:opacity .12s ease}
.chat-workspace__session:hover .chat-workspace__session-controls,.chat-workspace__session:has(:focus-visible) .chat-workspace__session-controls{opacity:1;pointer-events:auto}
.chat-workspace__session:hover .chat-workspace__session-title time,.chat-workspace__session:has(:focus-visible) .chat-workspace__session-title time{opacity:0}
.chat-workspace__session-controls .el-button{margin:0}
.chat-workspace__session-controls :deep(.el-button.chat-session-more-btn){width:24px;min-width:24px;height:20px;min-height:20px;padding:0;line-height:18px;border-radius:5px;background:rgba(255,255,255,.94);border:1px solid #dce4ee;color:var(--chat-text-muted);font-size:14px}
.chat-workspace__session-controls :deep(.el-button.chat-session-more-btn:hover){background:#fff;border-color:#cbd5e1;color:var(--chat-text)}
.chat-compact-rename{width:100%;max-width:100%}

/* 舞台与空状态 */
.chat-workspace__stage{min-width:0;flex:1;background:var(--chat-stage-bg)}
.chat-workspace__empty{display:flex;height:100%;align-items:center;justify-content:center;flex-direction:column;gap:12px;color:var(--chat-text-faint);font-size:13px}
.chat-workspace__empty .el-icon{font-size:44px;color:#cbd5e1}
.chat-workspace__empty strong{font-weight:500;font-size:16px;color:var(--chat-text-muted)}

/* 最大化时的左侧导航栏 */
.chat-workspace__rail{display:flex;width:var(--chat-rail-w,64px);box-sizing:border-box;flex:none;flex-direction:column;align-items:center;gap:4px;min-height:0;overflow-y:auto;padding:14px 4px;border-right:1px solid var(--chat-border);background:var(--chat-rail-bg,#f1f5f9)}
.chat-workspace__user-avatar{display:grid;place-items:center;width:34px;height:34px;margin-bottom:12px;border-radius:10px;background:var(--color-primary);color:#fff;font-size:14px;font-weight:600}
.chat-workspace__rail>button,.chat-workspace__user-avatar{flex-shrink:0}
.chat-workspace__rail button{display:flex;flex-direction:column;align-items:center;gap:4px;width:54px;padding:8px 2px;border:0;border-radius:8px;background:transparent;color:var(--chat-text-muted);cursor:pointer;transition:background-color .14s ease,color .14s ease}
.chat-workspace__rail button:hover{background:var(--chat-active-bg);color:var(--chat-text)}
.chat-workspace__rail button.is-active{background:#fff;color:var(--color-primary-hover);font-weight:600;box-shadow:0 1px 3px rgba(15,23,42,.1)}
.chat-workspace__rail .el-icon{font-size:19px}
.chat-workspace__rail small{font-size:10.5px;line-height:1.2;white-space:nowrap}
.chat-workspace__rail :deep(.el-badge__content){font-size:9px;height:15px;line-height:15px;padding:0 4px}

/* 最大化与窄屏布局（行高见 chatHeader.css） */
.chat-workspace--maximized:not(.chat-workspace--narrow){display:grid;grid-template-columns:var(--chat-rail-w,64px) var(--chat-session-width) minmax(0,1fr)}
.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__body{display:contents}
.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__rail{grid-column:1;grid-row:1 / 3}
.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__sessions{grid-column:2;grid-row:1 / 3}
.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__header{grid-column:3;grid-row:1}
.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__stage{grid-column:3;grid-row:2}
.chat-workspace--narrow .chat-workspace__sessions{position:absolute;z-index:1;bottom:0;left:0;max-width:calc(100% - 16px);box-shadow:var(--el-box-shadow-light)}
.chat-workspace--narrow .chat-workspace__header{padding:0 8px;gap:4px}
.chat-workspace--narrow .chat-workspace__heading strong{font-size:13px}
.chat-workspace--narrow .chat-header-divider{margin:0 2px}
.chat-workspace--narrow .chat-workspace__subtitle{display:none}
.chat-workspace--narrow .chat-workspace__actions{gap:2px}
@media (hover: none){.chat-workspace__session-controls{position:static;opacity:1;pointer-events:auto}.chat-workspace__session:hover .chat-workspace__session-title time,.chat-workspace__session:focus-within .chat-workspace__session-title time{opacity:1}}
</style>

<style scoped src="./chatHeader.css" />

<style scoped>
.chat-session-panel{display:flex;flex-direction:column;flex:1;min-width:0;min-height:0;overflow:hidden;background:#f9fafc}
.chat-session-panel__grip{display:flex;align-items:center;justify-content:center;gap:10px;flex:none;height:24px;color:#64748b;cursor:grab;user-select:none}
.chat-session-panel__grip:active{cursor:grabbing}.chat-session-panel__grip button{border:0;background:transparent;font:inherit;font-size:11px;color:inherit;cursor:pointer}
.chat-session-panel .chat-workspace__recent-closed{display:flex;align-items:center;justify-content:space-between;gap:2px;padding:4px}
.chat-session-panel .chat-workspace__recent-closed :deep(.el-button){margin:0;padding:4px;height:24px;font-size:11px;white-space:nowrap}
.chat-session-panel .chat-workspace__recent-closed :deep(.annotation-favorites-trigger .el-icon){display:none}
.chat-session-panel .chat-workspace__recent-closed :deep(.el-button[aria-pressed="true"]){background:var(--color-primary-soft);font-weight:600}
.chat-session-bottom-target{display:none;flex:none;padding:10px;text-align:center;font-size:12px;color:#2563eb;border:2px dashed #93c5fd}
.chat-session-bottom-target.is-drop-target{display:block}
.chat-session-middle-host{display:flex;flex:none;flex-direction:column;width:300px;min-height:0;border-right:1px solid #e6eaf0;background:#f9fafc}
.chat-session-middle-host.is-drop-target{position:relative;z-index:20;outline:2px dashed #60a5fa;outline-offset:-3px}
.chat-session-middle-host>span{padding:12px;color:#2563eb;font-size:12px}
.chat-workspace--middle-list :deep(.chat-folder-tree){flex:1;max-height:none}
.chat-workspace--maximized.chat-workspace--middle-list:not(.chat-workspace--narrow){grid-template-columns:var(--chat-rail-w,64px) var(--chat-session-width) 300px minmax(0,1fr)}
.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-session-middle-host{grid-column:3;grid-row:1 / 3}
.chat-workspace--maximized.chat-workspace--middle-list:not(.chat-workspace--narrow) .chat-workspace__header,.chat-workspace--maximized.chat-workspace--middle-list:not(.chat-workspace--narrow) .chat-workspace__stage{grid-column:4}
</style>

<style scoped>
/* ===== 总结 / 通知 / 项目管理等整页面板 ===== */
.chat-workspace--summary .chat-workspace__stage{display:flex;flex-direction:column;min-height:0;overflow:hidden}
.chat-summary-content{flex:1;min-height:0;overflow:auto;padding:12px;background:#fff}
.chat-workspace--summary.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__stage,.chat-workspace--summary.chat-workspace--maximized:not(.chat-workspace--narrow) .chat-workspace__header{grid-column:2 / 4}
.chat-workspace--compact-header .chat-workspace__header{display:flex;flex-wrap:nowrap;height:48px;min-height:48px;padding:8px 12px;gap:12px}
.chat-workspace--compact-header .chat-workspace__heading{flex:1;min-width:0;height:24px;align-self:center}
.chat-workspace--compact-header .chat-fixed-window-controls{flex:none;margin-left:auto}
.chat-workspace--compact-header.chat-workspace--maximized:not(.chat-workspace--narrow){grid-template-rows:48px minmax(0,1fr)}

</style>

<style scoped>
/* ===== 手机端：仿微信的两级导航。列表页全屏显示分类与会话，点击后仅显示当前会话，左上角返回。 ===== */
.chat-workspace--mobile{background:#fff}
.chat-workspace--mobile .chat-workspace__header{position:relative;display:flex;flex-wrap:nowrap;align-items:center;gap:2px;height:52px;min-height:52px;padding:0 6px;border-bottom:1px solid var(--chat-border);cursor:default}
.chat-workspace--mobile .chat-workspace__header>.el-button{flex:none;width:var(--chat-control-h);height:var(--chat-control-h);margin:0;padding:6px;font-size:20px}
.chat-workspace--mobile .chat-workspace__heading{display:block;flex:1 1 auto;min-width:0;height:auto;overflow:hidden;align-self:center}
.chat-workspace--mobile .chat-workspace__heading>strong{display:block;font-size:17px;font-weight:600;line-height:28px;padding-left:6px}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-order-identity){display:block;min-width:0}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-order-identity__title){height:22px;font-size:15px;font-weight:600;line-height:22px}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-order-identity__details){height:18px;margin-top:0;overflow:hidden;font-size:11px;line-height:18px}
.chat-workspace--mobile .chat-workspace__heading :deep(.chat-project-managers){display:none}
.chat-workspace--mobile .chat-header-command-row{flex:none;height:var(--chat-control-h);overflow:visible;background:transparent}
.chat-workspace--mobile .chat-fixed-window-controls{flex:none;margin-left:0;background:transparent}
.chat-workspace--mobile .chat-workspace__body{min-height:0}
.chat-workspace--mobile .chat-workspace__sessions{position:static;top:auto;flex:1 1 auto;width:100%!important;max-width:none;border-right:0;background:#fff;box-shadow:none}
.chat-workspace--list .chat-workspace__stage{display:none}
.chat-workspace--mobile .chat-workspace__session-tools{padding:8px 10px 6px}
.chat-workspace--mobile .chat-search-mode{width:76px}
.chat-workspace--mobile .chat-workspace__annotation-filters{padding:0 10px 6px;border-bottom:0}
.chat-workspace--mobile .chat-workspace__annotation-filters button{height:32px;font-size:13px}
.chat-workspace--mobile .chat-workspace__recent-closed{display:block}
.chat-workspace--mobile .chat-recent-closed-button{display:none}
.chat-workspace--mobile .chat-workspace__list{padding:0 0 6px;background:#fff}
.chat-workspace--mobile .chat-workspace__session{min-height:72px;padding:10px 12px;gap:12px;border-bottom:1px solid #f1f3f6;border-radius:0}
.chat-workspace--mobile .chat-workspace__session:hover,.chat-workspace--mobile .chat-workspace__session.is-active{background:transparent}
.chat-workspace--mobile .chat-workspace__session.is-pinned{background:#f7f8fa}
.chat-workspace--mobile .chat-workspace__session:active{background:#eceef2}
.chat-workspace--mobile .chat-workspace__session-left{width:48px;padding-top:0;align-self:center}
.chat-workspace--mobile .chat-session-member-count{display:none}
.chat-workspace--mobile .chat-workspace__avatar{width:48px;height:48px;border-radius:8px;font-size:20px}
.chat-workspace--mobile .chat-workspace__avatar--direct{border-radius:50%}
.chat-workspace--mobile .chat-workspace__session-left>.chat-workspace__avatar:only-child{margin-top:0}
.chat-workspace--mobile .chat-workspace__session-main{gap:4px}
.chat-workspace--mobile .chat-workspace__session-title strong{font-size:16px;font-weight:500}
.chat-workspace--mobile .chat-workspace__session-title time{font-size:12px}
.chat-workspace--mobile .chat-session-preview{font-size:13px}
.chat-workspace--mobile .chat-workspace__session-controls{align-self:center}
.chat-workspace--mobile .chat-workspace__pane-tabs{display:none}
.chat-workspace--mobile .chat-workspace__stage{background:#fff}
.chat-workspace--mobile.chat-workspace--summary .chat-workspace__stage{flex:1}
.chat-mobile-tabbar{display:flex;flex:none;align-items:stretch;border-top:1px solid var(--chat-border);background:var(--chat-sidebar-bg);padding-bottom:env(safe-area-inset-bottom)}
.chat-mobile-tabbar>button,.chat-mobile-tabbar>.el-tooltip__trigger{flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;height:54px;padding:4px 0;border:0;background:transparent;color:var(--chat-text-muted);font:inherit;font-size:11px;cursor:pointer}
.chat-mobile-tabbar .el-icon{font-size:24px}
.chat-mobile-tabbar .is-active{color:var(--color-primary);font-weight:600}
.chat-mobile-tabbar :deep(.el-badge__content){font-size:10px;height:16px;line-height:16px;padding:0 5px}
</style>

<style>
.chat-search-mode-options{z-index:100030!important}
.chat-mobile-group-popover{padding:6px!important}
.chat-mobile-group{display:flex;flex-direction:column}
.chat-mobile-group button{height:44px;border:0;border-bottom:1px solid #f1f3f6;background:transparent;color:#334155;font:inherit;font-size:15px;text-align:left;padding:0 12px;cursor:pointer}
.chat-mobile-group button:last-child{border-bottom:0}
.chat-mobile-group button.is-active{color:var(--color-primary);font-weight:600}
</style>

<style scoped>
.chat-workspace__sessions{position:relative;container-type:inline-size}
@container (max-width: 300px){
  .chat-search-mode{width:60px}
}
.chat-workspace__split-handle{position:absolute;right:0;top:0;bottom:0;width:6px;z-index:3;cursor:col-resize;touch-action:none;transition:background-color .14s ease}
.chat-workspace__split-handle:hover,.chat-workspace__split-handle:focus-visible{background:#cbd5e1;outline:0}
</style>

<style scoped src="./chatSidebar.css" />
