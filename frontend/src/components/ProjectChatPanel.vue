<template>
  <div ref="interactionRoot" :class="['project-chat-panel', { 'project-chat-panel--drawer': drawerMode, 'project-chat-panel--compact': compact, 'project-chat-panel--conversation': conversationMode, 'project-chat-panel--search-side': searchOpen && historyPlacement === 'side' }]">
    <el-empty v-if="!projectId" description="请先选择项目" :image-size="compact ? 56 : 72" />
    <div v-else class="project-chat-panel__main">
      <Teleport :to="headerReady && toolbarTarget ? toolbarTarget : 'body'" :disabled="!toolbarTarget || !headerReady"><div v-show="!toolbarTarget || active" class="chat-toolbar" :class="{ 'chat-toolbar--header': toolbarTarget }">
        <div class="chat-toolbar__title">
          <span v-if="!conversationMode">项目沟通</span>
          <el-tag v-if="!alwaysEnabled" :type="settings.enabled ? 'success' : 'info'" effect="plain">
            {{ settings.enabled ? '已开启' : '未开启' }}
          </el-tag>
        </div>
        <div class="chat-toolbar__actions">
          <el-button
            v-if="canAddToProgress && eligibleProgressMessages.length && !progressSelectionMode"
            type="default"
            :size="compact ? 'small' : 'default'"
            plain
            @click="toggleProgressSelectionMode"
          >
            批量选择
          </el-button>
          <el-tag v-if="canAddToProgress && progressSelectionMode" type="primary" effect="plain">批量选择中</el-tag>
          <el-popover
            v-if="collapsibleFilters"
            v-model:visible="filterPopoverVisible"
            trigger="click"
            placement="bottom-end"
            width="min(560px, calc(100vw - 32px))"
            popper-class="chat-filter-popover"
          >
            <template #reference>
              <el-button :type="activeFilterCount ? 'primary' : 'default'" :size="compact ? 'small' : 'default'" plain>
                查询筛选<span v-if="activeFilterCount">（{{ activeFilterCount }}）</span>
              </el-button>
            </template>
            <AppForm :model="filters" label-position="top" size="small" class="chat-filter-bar chat-filter-bar--popover">
              <el-form-item label="关键词" class="chat-filter-bar__field">
                <el-input v-model="filters.keyword" clearable placeholder="搜索消息内容" @keyup.enter="handleSearch" />
              </el-form-item>
              <el-form-item label="发送人" class="chat-filter-bar__field">
                <el-select v-model="filters.senderUserId" clearable filterable placeholder="全部发送人">
                  <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="时间范围" class="chat-filter-bar__range">
                <el-date-picker
                  v-model="filters.dateRange"
                  type="datetimerange"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  range-separator="至"
                  start-placeholder="开始"
                  end-placeholder="结束"
                  format="YYYY-MM-DD HH:mm"
                  time-format="HH:mm"
                  :show-now="true"
                  :show-confirm="true"
                  :show-footer="true"
                />
              </el-form-item>
              <el-form-item class="chat-filter-bar__favorite">
                <el-checkbox v-model="filters.favoritesOnly" @change="handleSearch">只看收藏</el-checkbox>
              </el-form-item>
              <el-form-item class="chat-filter-bar__actions">
                <el-button @click="handleResetSearch">重置</el-button>
                <el-button type="primary" @click="handleSearch">查询</el-button>
              </el-form-item>
            </AppForm>
          </el-popover>
          <el-switch
            v-if="!alwaysEnabled && settings.canManage"
            v-model="settings.enabled"
            :loading="settingsLoading || toggleLoading"
            inline-prompt
            active-text="开"
            inactive-text="关"
            @change="handleToggle"
          />
        </div>
      </div></Teleport>
      <div v-if="!alwaysEnabled && !conversationMode" class="chat-toolbar__hint">交接与继承记录始终可见；普通留言由管理员或项目经理开启。</div>

      <el-alert
        v-if="!alwaysEnabled && !settings.enabled"
        type="info"
        :closable="false"
        show-icon
        :title="settings.canManage ? '当前项目沟通未开启，可在右上角打开。' : '当前项目沟通未开启。'"
      />

      <AppForm v-if="conversationMode && conversationFiltersVisible" :model="filters" label-position="top" size="small" class="chat-filter-bar chat-filter-bar--popover chat-filter-panel">
        <el-form-item label="关键词" class="chat-filter-bar__field">
          <el-input v-model="filters.keyword" clearable placeholder="搜索消息内容" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="发送人" class="chat-filter-bar__field">
          <el-select v-model="filters.senderUserId" clearable filterable placeholder="全部发送人">
            <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围" class="chat-filter-bar__range">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            value-format="YYYY-MM-DD HH:mm:ss"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            format="YYYY-MM-DD HH:mm"
            time-format="HH:mm"
            :show-now="true"
            :show-confirm="true"
            :show-footer="true"
          />
        </el-form-item>
        <el-form-item class="chat-filter-bar__favorite">
          <el-checkbox v-model="filters.favoritesOnly" @change="handleSearch">只看收藏</el-checkbox>
        </el-form-item>
        <el-form-item class="chat-filter-bar__actions">
          <el-button @click="handleResetSearch">重置</el-button>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </el-form-item>
      </AppForm>

      <div v-if="conversationMode" class="chat-conversation-wrap">
        <el-button v-if="unreadMentions.length" class="chat-mention-jump" size="small" type="warning" @click="nextUnreadMention">{{ unreadMentions.length }} 条消息@了你</el-button>
        <el-scrollbar ref="chatListRef" v-loading="messagesLoading" class="chat-list chat-list--conversation" @scroll="handleConversationScroll">
          <div v-if="messages.length" class="chat-conversation">
            <div v-if="loadingEarlier" class="chat-conversation__notice">正在加载更早的消息…</div>
            <div v-else-if="!hasEarlierMessages && messages.length > conversationPageSize" class="chat-conversation__notice">已经到最早的消息了</div>
            <template v-for="item in conversationItems" :key="item.key">
              <div v-if="item.type === 'date'" v-show="showMessageDates" class="chat-date-divider"><span>{{ item.label }}</span></div>
              <ChatRecalledMessage v-else-if="item.message.recalledAt" :message="item.message" :can-reedit="recallDrafts.canReedit(item.message)" @reedit="reeditMessage" />
              <div v-else-if="item.isSystem" class="chat-system-message">
                <div class="chat-system-message__bar">
                  <el-tag size="small" :type="item.message.messageType === 'claim' ? 'warning' : 'success'" effect="plain">
                    {{ item.message.messageType === 'claim' ? '继承记录' : '交接记录' }}
                  </el-tag>
                  <span>{{ item.message.content }}</span>
                </div>
                <div v-if="item.message.metadata?.tasks?.length" class="handover-task-list">
                  <div v-for="task in item.message.metadata.tasks" :key="task.workflowInstanceId">
                    <strong>{{ task.orderNo }}</strong>
                    <span>{{ task.taskName }}</span>
                    <span>{{ task.fromUserName }} → {{ task.toUserName }}</span>
                  </div>
                </div>
                <span v-if="showMessageTime" class="chat-system-message__time">{{ chatMessageTime(item.message.createdAt) }}</span>
              </div>
              <div
                v-else
                class="chat-conversation-item" :ref="el=>messageInteractions.observe(el,item.message)"
                :data-message-id="item.message.id"
                :class="{ 'chat-conversation-item--own': item.isOwn, 'chat-conversation-item--grouped': !item.groupStart, 'chat-conversation-item--highlight': highlightedMessageId === String(item.message.id), 'chat-conversation-item--mentioned': mentionsMe(item.message) }"
              >
                <div v-if="!item.isOwn" class="chat-conversation-item__avatar">
                  <span v-if="item.groupStart" class="chat-avatar">{{ avatarText(item.message.senderName) }}</span>
                </div>
                <div class="chat-conversation-item__main">
                  <div class="chat-conversation-item__meta">
                    <strong v-if="!item.isOwn && item.groupStart">{{ item.message.senderName || '未知用户' }}</strong>
                    <span v-if="showMessageTime" class="chat-conversation-item__time" :title="chatMessageTime(item.message.createdAt)">{{ chatMessageTime(item.message.createdAt) }}</span>
                    <el-tag
                      v-for="mention in messageMentions(item.message).slice(0, 3)"
                      :key="mention.mentionedUserId"
                      size="small"
                      type="warning"
                      effect="plain"
                    >
                      @{{ mention.mentionedUserName }}
                    </el-tag>
                    <el-tooltip
                      v-if="messageMentions(item.message).length > 3"
                      :content="messageMentions(item.message).slice(3).map(entry => `@${entry.mentionedUserName}`).join('、')"
                      placement="top"
                    >
                      <el-tag size="small" type="warning" effect="plain">+{{ messageMentions(item.message).length - 3 }}</el-tag>
                    </el-tooltip>
                  </div>
                  <div class="chat-conversation-item__bubble-row">
                    <div class="chat-bubble" :class="{ 'chat-bubble--own': item.isOwn }" tabindex="0" data-message-menu-anchor @contextmenu="messageMenuRef.open($event,item.message)" @keydown="messageMenuRef.openKeyboard($event,item.message)">
                      <button v-if="item.message.reply" class="group-reply" @click="references.open(item.message.reply.id,$event)">{{ item.message.reply.senderName }}：{{ item.message.reply.content }}</button>
                      <div @click="openMessageReferences(item.message,$event)"><div v-if="textOnly" class="chat-bubble__text"><ScreenshotText :text="item.message.content" :chat-message-id="item.message.id" /></div>
                      <ScreenshotText v-else-if="screenshotIds(item.message.content).length" :text="item.message.content" :chat-message-id="item.message.id" /><RichTextContent v-else :document="highlightedMentionDocument(item.message)" :fallback="item.message.content" /></div>
                      <el-tag v-if="item.message.topicPath" size="small" effect="plain" class="chat-visible-topic">{{ item.message.topicPath }}</el-tag>
                      <div v-if="item.message.attachments?.length" class="message-attachments">
                        <div v-for="attachment in item.message.attachments" :key="attachment.id" class="message-attachment">
                          <a v-if="attachmentUrls[attachment.id]" :href="attachmentUrls[attachment.id]" target="_blank" rel="noopener">
                            <img :src="attachmentUrls[attachment.id]" :alt="attachment.originalName" />
                            <span>{{ attachment.originalName }}</span>
                          </a>
                          <template v-else>
                            <span>{{ attachment.originalName }}</span>
                            <span role="status">{{ attachmentErrors[attachment.id] || '图片加载中…' }}</span>
                            <el-button v-if="attachmentErrors[attachment.id]" size="small" link type="primary"
                              @click.stop="retryAttachment(attachment)">重新加载图片</el-button>
                          </template>
                        </div>
                      </div>
                    </div>
                    <div class="chat-conversation-item__tools">
                      <button type="button" class="chat-message-more" aria-label="消息操作" @click="messageMenuRef.open($event,item.message)">⋯</button>
                    </div>
                  </div>
                  <ChatMessageActions v-if="item.message.messageType === 'user'" :message="item.message" :current-user-id="currentUserId" :stats="messageInteractions.stats[item.message.id]" :views-available="messageInteractions.viewsAvailable.value" :acknowledging="acknowledgementSavingIds.has(item.message.id)" @reply="startMessageReply" @acknowledge="handleAcknowledgementToggle" @references="(id,event)=>references.open(id,event)" />
                </div>
              </div>
            </template>
          </div>
          <el-empty v-else description="暂无沟通记录" :image-size="56" />
        </el-scrollbar>
        <button v-if="viewingHistory || pendingNewCount" type="button" class="chat-new-message-tip" @click="viewingHistory ? returnToLatest() : handleNewMessageTipClick()">
          {{ viewingHistory ? (pendingNewCount ? `返回最新消息（${pendingNewCount} 条新消息）` : '返回最新消息') : `有 ${pendingNewCount} 条新消息，点击查看` }}
        </button>
      </div>

      <AppForm v-if="!conversationMode && !collapsibleFilters" :inline="true" :model="filters" size="small" class="chat-filter-bar">
          <el-form-item label="关键词" class="chat-filter-bar__field">
            <el-input v-model="filters.keyword" clearable :placeholder="compact ? '搜索消息内容' : '搜消息内容'" style="width: 180px" @keyup.enter="handleSearch" />
          </el-form-item>
          <el-form-item label="发送人" class="chat-filter-bar__field">
            <el-select v-model="filters.senderUserId" clearable filterable :placeholder="compact ? '发送人' : '全部'" style="width: 180px">
              <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围" class="chat-filter-bar__range">
            <el-date-picker
              v-model="filters.dateRange"
              type="datetimerange"
              value-format="YYYY-MM-DD HH:mm:ss"
              range-separator="至"
              start-placeholder="开始"
              end-placeholder="结束"
              format="YYYY-MM-DD HH:mm"
              time-format="HH:mm"
              :show-now="true"
              :show-confirm="true"
              :show-footer="true"
            />
          </el-form-item>
          <el-form-item class="chat-filter-bar__favorite">
            <el-checkbox v-model="filters.favoritesOnly" @change="handleSearch">只看收藏</el-checkbox>
          </el-form-item>
          <el-form-item class="chat-filter-bar__actions">
            <el-button type="primary" @click="handleSearch">查询</el-button>
            <el-button @click="handleResetSearch">重置</el-button>
          </el-form-item>
        </AppForm>

        <el-scrollbar v-if="!conversationMode" ref="chatListRef" v-loading="messagesLoading" :max-height="chatListMaxHeight" class="chat-list">
          <div v-if="messages.length" class="chat-list__items">
            <div
              v-for="message in messages"
              :key="message.id"
              class="chat-message-card" :ref="el=>messageInteractions.observe(el,message)"
              :class="{
                'chat-message-card--selected': isProgressMessageSelected(message),
                'chat-message-card--selectable': progressSelectionMode && String(message.content || '').trim(),
                'chat-message-card--context-active': messageMenuRef?.activeMessageId === String(message.id)
              }"
              @click="handleProgressMessageCardClick($event, message)"
               :data-message-id="message.id" tabindex="0" data-message-menu-anchor
              @contextmenu="messageMenuRef.open($event,message)" @keydown="messageMenuRef.openKeyboard($event,message)"
            >
              <ChatRecalledMessage v-if="message.recalledAt" :message="message" :can-reedit="recallDrafts.canReedit(message)" @reedit="reeditMessage" />
              <template v-else>
              <div class="chat-message-card__meta">
                <div class="chat-message-card__author">
                  <el-checkbox
                    v-if="progressSelectionMode && String(message.content || '').trim()"
                    :model-value="isProgressMessageSelected(message)"
                    :aria-label="`选择 ${message.senderName || '未知用户'} 的消息`"
                    @click.stop
                    @change="checked => handleProgressMessageSelection(message, checked)"
                  />
                  <strong>{{ message.senderName || '未知用户' }}</strong>
                  <el-tag v-if="message.messageType !== 'user'" size="small" :type="message.messageType === 'claim' ? 'warning' : 'success'" effect="plain">
                    {{ message.messageType === 'claim' ? '继承记录' : '交接记录' }}
                  </el-tag>
                  <el-tag
                    v-for="mention in messageMentions(message).slice(0, 3)"
                    :key="mention.mentionedUserId"
                    size="small"
                    type="warning"
                    effect="plain"
                  >
                    @{{ mention.mentionedUserName }}
                  </el-tag>
                  <el-tooltip
                    v-if="messageMentions(message).length > 3"
                    :content="messageMentions(message).slice(3).map(item => `@${item.mentionedUserName}`).join('、')"
                    placement="top"
                  >
                    <el-tag size="small" type="warning" effect="plain">+{{ messageMentions(message).length - 3 }}</el-tag>
                  </el-tooltip>
                </div>
                <div class="chat-message-card__tools">
                  <span v-if="showMessageTime">{{ chatMessageTime(message.createdAt) }}</span>
                  <el-tag v-if="message.topicPath" size="small" effect="plain" class="chat-visible-topic">{{ message.topicPath }}</el-tag>
                  <button type="button" class="chat-message-more" aria-label="消息操作" @click.stop="messageMenuRef.open($event,message)">⋯</button>
                </div>
              </div>
              <div
                v-if="textOnly"
                class="chat-message-card__content"
              ><ScreenshotText :text="message.content" :chat-message-id="message.id" /></div>
              <ScreenshotText v-else-if="screenshotIds(message.content).length" :text="message.content" :chat-message-id="message.id" /><RichTextContent v-else :document="message.contentJson" :fallback="message.content" />
              <div v-if="message.metadata?.tasks?.length" class="handover-task-list">
                <div v-for="task in message.metadata.tasks" :key="task.workflowInstanceId">
                  <strong>{{ task.orderNo }}</strong>
                  <span>{{ task.taskName }}</span>
                  <span>{{ task.fromUserName }} → {{ task.toUserName }}</span>
                </div>
              </div>
              <div v-if="message.attachments?.length" class="message-attachments">
                <div v-for="attachment in message.attachments" :key="attachment.id" class="message-attachment">
                          <a v-if="attachmentUrls[attachment.id]" :href="attachmentUrls[attachment.id]" target="_blank" rel="noopener">
                            <img :src="attachmentUrls[attachment.id]" :alt="attachment.originalName" />
                            <span>{{ attachment.originalName }}</span>
                          </a>
                          <template v-else>
                            <span>{{ attachment.originalName }}</span>
                            <span role="status">{{ attachmentErrors[attachment.id] || '图片加载中…' }}</span>
                            <el-button v-if="attachmentErrors[attachment.id]" size="small" link type="primary"
                              @click.stop="retryAttachment(attachment)">重新加载图片</el-button>
                          </template>
                        </div>
              </div>
              <ChatMessageActions v-if="message.messageType === 'user'" :message="message" :current-user-id="currentUserId" :stats="messageInteractions.stats[message.id]" :views-available="messageInteractions.viewsAvailable.value" :acknowledging="acknowledgementSavingIds.has(message.id)" @reply="startMessageReply" @acknowledge="handleAcknowledgementToggle" @references="(id,event)=>references.open(id,event)" />
              </template>
            </div>
          </div>
          <el-empty v-else description="暂无沟通记录" :image-size="compact ? 56 : 72" />
        </el-scrollbar>

        <div v-if="canAddToProgress && progressSelectionMode" class="chat-batch-action-bar">
          <div class="chat-batch-action-bar__summary">
            <strong>已选 {{ selectedProgressMessages.length }} 条</strong>
            <span :class="{ 'is-over-limit': selectedProgressCharacterCount > 10000 }">
              预计 {{ selectedProgressCharacterCount }} / 10000 字
            </span>
            <span class="chat-batch-action-bar__hint">点击卡片选择，Shift + 点击可连续选择</span>
          </div>
          <div class="chat-batch-action-bar__actions">
            <el-button size="small" @click="handleSelectAllPage">{{ allProgressMessagesSelected ? '取消全选' : '全选本页' }}</el-button>
            <el-button size="small" :disabled="!selectedProgressMessages.length" @click="clearProgressSelection()">清空</el-button>
            <el-button size="small" @click="clearProgressSelection(true)">退出</el-button>
            <el-button
              type="primary"
              size="small"
              :disabled="!selectedProgressMessages.length || selectedProgressCharacterCount > 10000"
              @click="handleAddSelectedToProgress"
            >
              合并为进度
            </el-button>
          </div>
        </div>

        <div v-if="!conversationMode" class="chat-pagination">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.limit"
            :page-sizes="[10, 20, 50]"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            small
            @current-change="handlePageChange"
            @size-change="handlePageSizeChange"
          />
        </div>

        <div v-if="settings.enabled && !conversationMode" class="chat-composer">
          <div v-if="replyToMessage" class="group-compose-reply">回复 {{ replyToMessage.senderName }}：{{ replyToMessage.content }}<el-button link @click="replyToMessage=null">取消引用</el-button></div>
          <div class="chat-composer__header">
            <span>发送消息</span>
            <div class="chat-composer__mention-wrap">
              <el-select
                v-model="composer.mentionedUserIds"
                @visible-change="desktopPresenceOpen = $event"
                popper-class="chat-mention-user-options"
                multiple
                clearable
                filterable
                collapse-tags
                collapse-tags-tooltip
                :max-collapse-tags="compact ? 1 : 3"
                :multiple-limit="20"
                placeholder="@提醒用户（可多选）"
                class="chat-composer__mention"
              >
                <el-option-group v-for="section in mentionUserGroups" :key="section.label" :label="section.label"><el-option v-for="user in section.users" :key="user.id" :label="user.full_name || user.username" :value="user.id"><span>{{ user.full_name || user.username }}</span><ChatDesktopPresence v-if="user.id!=='__all__'" class="mention-desktop-state" :online="desktopPresence[user.id]" :work-status="workStatuses[user.id]" :loading="desktopPresenceLoading" /></el-option></el-option-group>
              </el-select>
              <span class="chat-composer__mention-count">{{ composer.mentionedUserIds.length }}/20</span>
            </div>
          </div>
          <div class="chat-composer__body" data-screenshot-editor="own" @paste.capture="handleComposerPaste">
            <el-input
              v-if="textOnly"
              v-model="composer.content"
              :disabled="sending"
              type="textarea"
              :autosize="compact ? { minRows: 2, maxRows: 4 } : false"
              :rows="compact ? undefined : 4"
              maxlength="10000"
              show-word-limit
              placeholder="输入项目沟通内容…"
            />
            <RichTextComposer ref="richComposerRef" external-images
              v-else
              v-model="composer.contentJson"
              :disabled="sending"
              placeholder="输入项目沟通内容…"
              @update:plain-text="composer.content = $event"
            />
            <div class="chat-composer__actions">
              <el-button
                type="primary"
                :loading="sending"
                :disabled="sending || imagesBlocked || (!composer.content.trim() && !pendingImages.length)"
                @click="handleSend"
              >
                发送消息
              </el-button>
            </div>
          </div>
          <ChatImageAttachments v-if="attachmentsEnabled" :items="pendingImages" :disabled="sending"
            @add="addComposerImages" @retry="imageQueue.retry" @remove="imageQueue.remove" />
        </div>

        <div v-if="settings.enabled && conversationMode" class="chat-composer chat-composer--conversation" data-screenshot-editor="own" @paste.capture="handleComposerPaste">
          <div v-if="replyToMessage" class="group-compose-reply">回复 {{ replyToMessage.senderName }}：{{ replyToMessage.content }}<el-button link @click="replyToMessage=null">取消引用</el-button></div>
          <button type="button" class="chat-composer-resize" aria-label="调整输入区高度" title="拖动调整输入区高度" @pointerdown="startComposerResize" @keydown="resizeComposerByKeyboard" />
          <div v-if="composer.mentionedUserIds.length" class="chat-composer__mention-tags">
            <el-tag
              v-for="userId in composer.mentionedUserIds"
              :key="userId"
              size="small"
              type="warning"
              effect="plain"
              closable
              @close="removeMention(userId)"
            >
              @{{ userNameById(userId) }}
            </el-tag>
          </div>
          <div class="chat-composer__input-row">
            <el-popover
              v-model:visible="mentionPopoverVisible"
              trigger="click"
              placement="top-start"
              :width="280"
              @hide="handleMentionPopoverHide"
            >
              <template #reference>
                <span class="chat-composer__mention-anchor" aria-hidden="true" />
              </template>
              <div @keydown.esc.capture.stop.prevent="handleMentionEscape">
                <el-select
                  ref="mentionSelectRef"
                  v-model="composer.mentionedUserIds"
                @visible-change="desktopPresenceOpen = $event"
                popper-class="chat-mention-user-options"
                  multiple
                  filterable
                  :automatic-dropdown="automaticMentionActive"
                  collapse-tags
                  collapse-tags-tooltip
                  :multiple-limit="20"
                  placeholder="选择要提醒的用户"
                  style="width: 100%"
                  @change="handleMentionSelectionChange"
                >
                  <el-option-group v-for="section in mentionUserGroups" :key="section.label" :label="section.label"><el-option v-for="user in section.users" :key="user.id" :label="user.full_name || user.username" :value="user.id"><span>{{ user.full_name || user.username }}</span><ChatDesktopPresence v-if="user.id!=='__all__'" class="mention-desktop-state" :online="desktopPresence[user.id]" :work-status="workStatuses[user.id]" :loading="desktopPresenceLoading" /></el-option></el-option-group>
                </el-select>
              </div>
            </el-popover>
            <el-input
              v-if="textOnly"
              ref="composerInputRef"
              v-model="composer.content"
              :disabled="sending"
              type="textarea"
              :rows="3" :input-style="composerInputStyle" resize="none"
              maxlength="10000"
              placeholder="Enter 发送，Shift+Enter 换行"
              @input="handleComposerInput"
              @compositionstart="handleComposerCompositionStart"
              @compositionend="handleComposerCompositionEnd"
              @keydown="handleComposerKeydown"
            />
            <RichTextComposer ref="richComposerRef" external-images
              v-else
              v-model="composer.contentJson"
              :disabled="sending"
              placeholder="输入项目沟通内容…"
              @update:plain-text="composer.content = $event"
            />
            <el-button
              type="primary"
              :loading="sending"
              :disabled="sending || imagesBlocked || (!composer.content.trim() && !pendingImages.length)"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
          <ChatImageAttachments v-if="attachmentsEnabled" :items="pendingImages" :disabled="sending"
            @add="addComposerImages" @retry="imageQueue.retry" @remove="imageQueue.remove" />
        </div>
    </div>
    <ChatHistorySearchPanel
      v-if="conversationMode && projectId"
      v-model:visible="searchOpen"
      :project-id="projectId"
      :project-type="projectType"
      :senders="historySenders"
      :allow-files="projectType === 'annotation'"
      :placement="historyPlacement"
      @locate="locateMessage"
    />
    <small v-if="draft.error.value" role="alert">{{draft.error.value}}</small>
    <ChatMessageReferences ref="references" :project-id="projectId" :project-type="projectType" @locate="locateMessage" />
    <ChatMessageContextMenu ref="messageMenuRef" :messages="messages" :current-user-id="currentUserId" :handlers="messageMenuHandlers" :can-progress="canAddToProgress" :selecting="progressSelectionMode" :active="active" />
  </div>
</template>

<script setup>
import ChatDesktopPresence from '@/components/chat/ChatDesktopPresence.vue'
import { useDesktopPresence } from '@/composables/useDesktopPresence'
import ChatRecalledMessage from './chat/ChatRecalledMessage.vue'
import { useRecalledMessageDrafts } from '@/composables/useRecalledMessageDrafts'
import { combineRecallDraft } from '@/utils/recallDrafts'
import { projectMentionOrder } from '@/utils/projectMentionOrder'
import { useAnnotationMentionManagers } from '@/composables/useAnnotationMentionManagers'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { screenshotIds } from '@/utils/screenshotReferences'
import { useChatMessageInteractions } from '@/composables/useChatMessageInteractions'
import ChatMessageActions from './chat/ChatMessageActions.vue'
import ChatMessageReferences from './chat/ChatMessageReferences.vue'

import ChatMessageContextMenu from './chat/ChatMessageContextMenu.vue'
import { chatAvatarText, chatDayKey, chatGroupStart } from '@/utils/chatLayout'
import { useChatTimeDisplay } from '@/composables/useChatTimeDisplay'
const { formatMessageTime: chatMessageTime, formatMessageDay, showMessageTime, showMessageDates } = useChatTimeDisplay()
import { topicApi } from '@/api/chatTopics'
import { useChatTopics } from '@/composables/useChatTopics'
import { messageTopicPatch, newChatRequestId } from '@/utils/chatTopics'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatComposerHeight } from '@/composables/useChatComposerHeight'
import { formatBusinessDateTime as formatDateTime } from '@/utils/dateTime'
import { chatRequest } from '@/api/projectChat'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { mentionedDocument } from '@/utils/chatMentions'
import {useChatDraft} from '@/composables/useChatDraft'
import {draftImages} from '@/utils/chatDrafts'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { copyTextToClipboard } from '@/utils/clipboard'
import { ensureConnected, subscribe } from '@/utils/realtimeSocket'
import {
  acknowledgeProjectChatMessage,
  createProjectChatMessage,
  recallProjectChatMessage,
  favoriteProjectChatMessage,
  getProjectChatAttachmentBlob,
  getProjectChatMessages,
  getProjectChatSettings,
  updateProjectChatSettings,
  unacknowledgeProjectChatMessage,
  unfavoriteProjectChatMessage,
  uploadProjectChatAttachment
} from '@/api/projectChat'
import ChatImageAttachments from '@/components/chat/ChatImageAttachments.vue'
import ChatHistorySearchPanel from '@/components/chat/ChatHistorySearchPanel.vue'
import { createChatImageQueue } from '@/utils/chatImageQueue'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'

const props = defineProps({
  targetMessageId: { type: String, default: '' },
  projectId: { type: [String, Number], default: '' },
  projectType: { type: String, default: 'translation' },
  active: { type: Boolean, default: false },
  drawerMode: { type: Boolean, default: false },
  textOnly: { type: Boolean, default: false },
  alwaysEnabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  collapsibleFilters: { type: Boolean, default: false },
  canAddToProgress: { type: Boolean, default: false },
  conversationMode: { type: Boolean, default: false },
  toolbarTarget: { type: String, default: '' },
  historyPlacement: { type: String, default: 'overlay' }
})

const emit = defineEmits(['add-to-progress', 'unread'])

const settings = reactive({ enabled: false, canManage: false })
const settingsLoading = ref(false)
const toggleLoading = ref(false)
const messagesLoading = ref(false)
const chatListRef = ref(null)
const composerInputRef = ref(null)
const richComposerRef = ref(null)
const mentionSelectRef = ref(null)
const sending = ref(false)
const { topics, refresh: refreshTopics } = useChatTopics()
let sendFingerprint = '', sendRequestId = ''
let unsubscribeTopicChanged
const pendingImages = reactive([])
const attachmentsEnabled = computed(() => !props.textOnly || props.projectType === 'annotation')
const imagesBlocked = computed(() => pendingImages.some(item => item.status !== 'ready'))
const imageQueue = createChatImageQueue(pendingImages, {
  upload: file=>uploadProjectChatAttachment(file,'chat'),
  createUrl: file => URL.createObjectURL(file),
  revokeUrl: url => URL.revokeObjectURL(url),
  warn: message => ElMessage.warning(message)
})
let composerGeneration = 0
const clearComposerImages = () => {
  composerGeneration++
  imageQueue.clear()
}
const addComposerImages = files => {
  if (!sending.value && attachmentsEnabled.value) imageQueue.add(files)
}
const handleComposerPaste = event => {
  if (!attachmentsEnabled.value) return
  const files = [...(event.clipboardData?.items || [])]
    .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
    .map(item => item.getAsFile()).filter(Boolean)
  if (!files.length) return
  // 有文字时保留浏览器原生粘贴，确保光标位置、撤销与文字输入一致。
  if (!event.clipboardData.getData('text/plain')) event.preventDefault()
  addComposerImages(files)
}
const userOptions = ref([])
const memberUserIds = ref([])
const desktopPresenceOpen = ref(false)
const { statuses: desktopPresence, workStatuses, loading: desktopPresenceLoading } = useDesktopPresence(computed(() => userOptions.value.map(user => user.id)), computed(() => props.active && desktopPresenceOpen.value))
const mentionProject = useAnnotationMentionManagers(computed(() => props.projectId), computed(() => props.projectType === 'annotation' && props.active && desktopPresenceOpen.value))
const mentionUserGroups = computed(() => {
  const users = [{ id:'__all__',full_name:'所有人',all:true },
    ...userOptions.value.filter(user => String(user.id) !== currentUserId && memberUserIds.value.includes(String(user.id))).map(user => ({ ...user, outside: false })),
    ...userOptions.value.filter(user => String(user.id) !== currentUserId && !memberUserIds.value.includes(String(user.id))).map(user => ({ ...user, outside: true })),
  ]
  const ordered = projectMentionOrder(users, props.projectType === 'annotation' ? mentionProject.value : null)
  const groups = new Map()
  for (const user of ordered) {
    const label = user.mentionSection || (user.all ? '群组提醒' : user.outside ? '未参与人员 · 发送后自动加入' : '群组参与人')
    if (!groups.has(label)) groups.set(label, { label, users: [] })
    groups.get(label).users.push(user)
  }
  return [...groups.values()]
})
const messages = ref([])
const interactionRoot = ref(), references = ref(), replyToMessage = ref(null)
const messageInteractions = useChatMessageInteractions({projectId:computed(()=>String(props.projectId)),projectType:computed(()=>props.projectType),messages,active:computed(()=>props.active)})
async function startMessageReply(message) { replyToMessage.value=message;await nextTick();interactionRoot.value?.querySelector('.chat-composer textarea, .chat-composer [contenteditable="true"]')?.focus() }
function openMessageReferences(message,event) { if(message.reply || messageInteractions.stats[message.id]?.replyCount)references.value.open(message.reply?.id||message.id,event) }

const favoriteSavingIds = ref(new Set())
const acknowledgementSavingIds = ref(new Set())
const filterPopoverVisible = ref(false)
const progressSelectionMode = ref(false)
const selectedProgressMessageIds = ref(new Set())
const lastSelectedProgressMessageId = ref('')
const messageMenuRef = ref(null)
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const conversationPageSize = 20
const currentUserId = String(localStorage.getItem('user_id') || '')
const { sessions: chatSessions, phaseOneEnabled, refresh: refreshSessions } = useAnnotationFollowed()
const chatSession = computed(() => chatSessions.value.find(s => s.key === `${props.projectType}:${props.projectId}`))
const seenMentions = ref([])
const unreadMentions = computed(() => (chatSession.value?.mentionMessageIds || []).filter(id => !seenMentions.value.includes(id)))
const mentionsMe = message => (message.mentions || []).some(m => String(m.mentionedUserId) === currentUserId)
const highlightedMentionDocument = message => mentionedDocument(message, currentUserId)
let readTimer = 0, readBusy = false, lastReadSequence = 0
async function nextUnreadMention() {
  const id = unreadMentions.value[0]
  if (!id) return
  await locateMessage(id)
  if (!props.active || !document.hasFocus()) return
  try {
    await chatRequest(`sessions/${props.projectType}/${props.projectId}/preferences`, { method: 'put', data: { readMessageId: id } })
    seenMentions.value.push(id); await refreshSessions()
  } catch (e) { ElMessage.error(getLocalizedErrorMessage(e, '更新已读失败')) }
}
function scheduleRead() { window.clearTimeout(readTimer); readTimer = window.setTimeout(markVisibleRead, 350) }
async function markVisibleRead() {
  if (document.querySelector('.chat-topic-results-dialog')) return
  if (!phaseOneEnabled.value || !props.active || !props.conversationMode || readBusy || unreadMentions.value.length || document.visibilityState !== 'visible' || !document.hasFocus()) return
  const wrap = getScrollWrap()
  if (!wrap) return
  const bounds = wrap.getBoundingClientRect()
  const visibleIds = [...wrap.querySelectorAll('[data-message-id]')].filter(el => {
    const box = el.getBoundingClientRect()
    return box.bottom > bounds.top && box.top < bounds.bottom
  }).map(el => el.dataset.messageId)
  const message = messages.value.filter(m => visibleIds.includes(String(m.id))).sort((a,b) => b.sequenceNo - a.sequenceNo)[0]
  if (!message || message.sequenceNo <= lastReadSequence) return
  readBusy = true
  try {
    await chatRequest(`sessions/${props.projectType}/${props.projectId}/preferences`, { method: 'put', data: { readMessageId: message.id } })
    lastReadSequence = message.sequenceNo; await refreshSessions()
  } catch { /* 下次回到前台时重试，不提前消除未读。 */ }
  finally { readBusy = false }
}
watch(() => props.targetMessageId, id => { if (id) locateMessage(id) })
const conversationFiltersVisible = ref(false)
const mentionPopoverVisible = ref(false)
const automaticMentionActive = ref(false)
const automaticMentionTriggerIndex = ref(-1)
const mentionIdsAtAutomaticTrigger = ref(new Set())
const composerIsComposing = ref(false)
const loadingEarlier = ref(false)
const pendingNewCount = ref(0)
const viewingHistory = ref(false)
const historyHasOlder = ref(false)
const searchOpen = ref(false)
const highlightedMessageId = ref('')
let highlightTimer = null
const filters = reactive({ keyword: '', senderUserId: '', dateRange: [], favoritesOnly: false })
const composer = reactive({
  content: '',
  contentJson: { type: 'doc', content: [{ type: 'paragraph' }] },
  mentionedUserIds: []
})
const recallDrafts = useRecalledMessageDrafts(computed(() => [props.projectType, props.projectId]))
async function reeditMessage(message) {
  if (sending.value) return
  const recovered = await recallDrafts.restore(message)
  if (!recovered || sending.value) return
  try {
    const result = combineRecallDraft({ content: composer.content, contentJson: composer.contentJson, mentionIds: composer.mentionedUserIds, replyTo: replyToMessage.value }, recovered)
    composer.content = result.content; composer.contentJson = result.contentJson
    composer.mentionedUserIds = result.mentionIds; replyToMessage.value = result.replyTo
    if (recovered.files.length) addComposerImages(recovered.files)
    if (recovered.files.length < recovered.attachmentCount) ElMessage.warning('原文已恢复，部分附件暂存不可用，请重新添加')
    sendRequestId = ''; sendFingerprint = ''; closeMentionPopover(); draft.persistNow(); recallDrafts.forget(message)
    await nextTick(); props.textOnly ? composerInputRef.value?.focus?.() : richComposerRef.value?.focus?.()
  } catch (e) { ElMessage.warning(e.message) }
}
const attachmentUrls = reactive({})
const attachmentErrors = reactive({})
const attachmentLoading = new Set()
const attachmentObjectUrls = new Set()
let attachmentUrlGeneration = 0
const chatListMaxHeight = computed(() => {
  if (props.conversationMode) return undefined
  return props.drawerMode ? 'calc(100vh - 360px)' : '420px'
})
const activeFilterCount = computed(() => [
  filters.keyword.trim(),
  filters.senderUserId,
  Array.isArray(filters.dateRange) && filters.dateRange.length === 2,
  filters.favoritesOnly
].filter(Boolean).length)
const automaticMentionEnabled = computed(() => (
  props.projectType === 'annotation' && props.textOnly && props.conversationMode
))
const eligibleProgressMessages = computed(() => messages.value.filter(message => String(message.content || '').trim()))
const selectedProgressMessages = computed(() => eligibleProgressMessages.value.filter(message => selectedProgressMessageIds.value.has(String(message.id))))
const selectedProgressCharacterCount = computed(() => selectedProgressMessages.value.reduce((total, message, index) => {
  const formatted = `【${message.senderName || '未知用户'}】\n${String(message.content || '').trim()}`
  return total + formatted.length + (index ? 2 : 0)
}, 0))
const allProgressMessagesSelected = computed(() => eligibleProgressMessages.value.length > 0 && selectedProgressMessages.value.length === eligibleProgressMessages.value.length)
let pollTimer = null
let unsubscribeChatMessage = null
let unsubscribeChatAcknowledgement = null
let unsubscribeSocketConnected = null
let newerMessageNoticeShown = false

const clearProgressSelection = (exitMode = false) => {
  selectedProgressMessageIds.value = new Set()
  lastSelectedProgressMessageId.value = ''
  if (exitMode) progressSelectionMode.value = false
}

const toggleProgressSelectionMode = () => {
  if (progressSelectionMode.value) return clearProgressSelection(true)
  progressSelectionMode.value = true
}

const isProgressMessageSelected = message => selectedProgressMessageIds.value.has(String(message?.id))

const handleProgressMessageSelection = (message, checked) => {
  const next = new Set(selectedProgressMessageIds.value)
  const id = String(message?.id)
  if (checked) next.add(id)
  else next.delete(id)
  selectedProgressMessageIds.value = next
  lastSelectedProgressMessageId.value = id
}

const handleProgressMessageCardClick = (event, message) => {
  if (!progressSelectionMode.value || !String(message?.content || '').trim()) return
  if (event.target.closest('button, a, input, label, [role="button"], [role="checkbox"]')) return
  if (window.getSelection?.()?.toString().trim()) return
  const id = String(message.id)
  const next = new Set(selectedProgressMessageIds.value)
  let rangeApplied = false
  if (event.shiftKey && lastSelectedProgressMessageId.value) {
    const lastIndex = eligibleProgressMessages.value.findIndex(item => String(item.id) === lastSelectedProgressMessageId.value)
    const currentIndex = eligibleProgressMessages.value.findIndex(item => String(item.id) === id)
    if (lastIndex >= 0 && currentIndex >= 0) {
      const [start, end] = [lastIndex, currentIndex].sort((a, b) => a - b)
      eligibleProgressMessages.value.slice(start, end + 1).forEach(item => next.add(String(item.id)))
      rangeApplied = true
    }
  }
  if (!rangeApplied) {
    if (next.has(id)) next.delete(id)
    else next.add(id)
  }
  selectedProgressMessageIds.value = next
  lastSelectedProgressMessageId.value = id
}

const handleSelectAllPage = () => {
  selectedProgressMessageIds.value = allProgressMessagesSelected.value
    ? new Set()
    : new Set(eligibleProgressMessages.value.map(message => String(message.id)))
  lastSelectedProgressMessageId.value = ''
}

const handleAddSelectedToProgress = () => {
  if (!selectedProgressMessages.value.length) return ElMessage.warning('请先选择需要添加的沟通消息')
  if (selectedProgressCharacterCount.value > 10000) return ElMessage.warning('所选消息超过具体进度 10000 字限制，请减少选择')
  emit('add-to-progress', [...selectedProgressMessages.value])
}

const closeProgressTextMenu = () => messageMenuRef.value?.close()
const messageMenuHandlers = {
  recall: async message=>{
    try{await ElMessageBox.confirm('撤回后其他用户将无法查看该消息，确定撤回？','确认撤回',{type:'warning',customClass:'chat-confirm-message-box'});await recallDrafts.remember(message, file=>getProjectChatAttachmentBlob(file.id));Object.assign(message,await recallProjectChatMessage(props.projectId,message.id))}
    catch(e){if(e!=='cancel'&&e!=='close')ElMessage.error(e.message||'撤回失败')}
  },
  reply: message=>startMessageReply(message),
  copy: async (message, excerpt) => {
    const copied = await copyTextToClipboard(excerpt || message.content || (message.attachments || []).map(file => file.originalName).join('\n'))
    copied ? ElMessage.success('已复制') : ElMessage.error('复制失败，请使用 Ctrl+C')
  },
  favorite: message => handleFavoriteToggle(message),
  acknowledge: message => handleAcknowledgementToggle(message),
  canAcknowledge: message => canAcknowledgeMessage(message),
  progress: (message, excerpt) => {
    const content = excerpt || message.content
    if (content.length > 10000) return ElMessage.warning('消息超过具体进度 10000 字限制，请先选择部分文字')
    emit('add-to-progress', [{ ...message, content }])
    window.getSelection?.()?.removeAllRanges()
  },
  select: message => {
    progressSelectionMode.value = true
    handleProgressMessageSelection(message, true)
    window.getSelection?.()?.removeAllRanges()
  },
}

const clearPolling = () => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const clearAttachmentUrls = () => {
  attachmentUrlGeneration++
  attachmentLoading.clear()
  Object.keys(attachmentErrors).forEach(key => delete attachmentErrors[key])
  attachmentObjectUrls.forEach(url => URL.revokeObjectURL(url))
  attachmentObjectUrls.clear()
  Object.keys(attachmentUrls).forEach(key => delete attachmentUrls[key])
}

const ensureAttachmentUrls = async (items) => {
  const generation = attachmentUrlGeneration
  const attachments = items.flatMap(item => item.attachments || [])
  await Promise.all(attachments.map(async (attachment) => {
    if (attachmentUrls[attachment.id] || attachmentLoading.has(attachment.id) || attachmentErrors[attachment.id]) return
    attachmentLoading.add(attachment.id)
    try {
      const blob = await getProjectChatAttachmentBlob(attachment.id)
      if (generation !== attachmentUrlGeneration || attachmentUrls[attachment.id]) return
      const url = URL.createObjectURL(blob)
      attachmentUrls[attachment.id] = url
      attachmentObjectUrls.add(url)
    } catch (error) {
      if (generation === attachmentUrlGeneration) {
        attachmentErrors[attachment.id] = error?.response?.status === 404
          ? '图片文件暂未找到' : '图片加载失败，请重试'
      }
    } finally {
      if (generation === attachmentUrlGeneration) attachmentLoading.delete(attachment.id)
    }
  }))
}

const retryAttachment = attachment => {
  delete attachmentErrors[attachment.id]
  return ensureAttachmentUrls([{ attachments: [attachment] }])
}

const buildMessageParams = (skip, limit) => ({
  skip,
  limit,
  keyword: filters.keyword || undefined,
  sender_user_id: filters.senderUserId || undefined,
  date_from: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[0] : undefined,
  date_to: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[1] : undefined,
  favorites_only: filters.favoritesOnly || undefined
})

const getScrollWrap = () => chatListRef.value?.wrapRef || null

const isConversationAtBottom = () => {
  const wrap = getScrollWrap()
  if (!wrap) return true
  return wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < 40
}

const scrollConversationToBottom = () => {
  const wrap = getScrollWrap()
  if (wrap) wrap.scrollTop = wrap.scrollHeight
}

const conversationLoadLatest = async ({ scrollToEnd = true } = {}) => {
  if (!props.projectId) {
    messages.value = []
    pagination.total = 0
    return
  }
  messagesLoading.value = true
  try {
    const res = await getProjectChatMessages(props.projectId, buildMessageParams(0, conversationPageSize), props.projectType)
    settings.enabled = !!res?.enabled
    if (typeof res?.canManage === 'boolean') settings.canManage = res.canManage
    // 后端按时间倒序返回，会话视图反转为正序展示。
    messages.value = (Array.isArray(res?.items) ? res.items : []).slice().reverse()
    pagination.total = Number(res?.total || 0)
    viewingHistory.value = false
    historyHasOlder.value = false
    pendingNewCount.value = 0
    await ensureAttachmentUrls(messages.value)
    if (scrollToEnd) {
      await nextTick()
      scrollConversationToBottom()
    }
  } catch (error) {
    messages.value = []
    pagination.total = 0
    ElMessage.error(getLocalizedErrorMessage(error, '加载沟通记录失败'))
  } finally {
    messagesLoading.value = false
    scheduleRead()
  }
}

const hasEarlierMessages = computed(() => (
  viewingHistory.value ? historyHasOlder.value : messages.value.length < pagination.total
))
const historySenders = computed(() => userOptions.value.map(user => ({
  id: user.id,
  name: user.full_name || user.username,
})))

// 滚动到顶部加载更早消息，并保持原滚动锚点不跳动。
const loadMessagesBeforeAnchor = async () => {
  const oldest = messages.value[0]
  if (!oldest?.createdAt || !oldest?.id) return
  loadingEarlier.value = true
  const wrap = getScrollWrap()
  const prevHeight = wrap?.scrollHeight || 0
  const prevTop = wrap?.scrollTop || 0
  try {
    const res = await getProjectChatMessages(props.projectId, {
      before_created_at: oldest.createdAt,
      before_id: oldest.id,
      limit: conversationPageSize,
    }, props.projectType)
    const existingIds = new Set(messages.value.map(item => String(item.id)))
    const older = (Array.isArray(res?.items) ? res.items : []).filter(item => !existingIds.has(String(item.id)))
    if (older.length) {
      messages.value = [...older, ...messages.value]
      await ensureAttachmentUrls(older)
    }
    historyHasOlder.value = !!res?.hasOlder
    await nextTick()
    if (wrap) wrap.scrollTop = wrap.scrollHeight - prevHeight + prevTop
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '加载更早的消息失败'))
  } finally {
    loadingEarlier.value = false
  }
}

const loadEarlierMessages = async () => {
  if (!props.conversationMode || !hasEarlierMessages.value || loadingEarlier.value || messagesLoading.value) return
  if (viewingHistory.value) return loadMessagesBeforeAnchor()
  loadingEarlier.value = true
  const wrap = getScrollWrap()
  const prevHeight = wrap?.scrollHeight || 0
  const prevTop = wrap?.scrollTop || 0
  try {
    const res = await getProjectChatMessages(
      props.projectId,
      buildMessageParams(messages.value.length, conversationPageSize),
      props.projectType
    )
    const existingIds = new Set(messages.value.map(item => String(item.id)))
    const older = (Array.isArray(res?.items) ? res.items : [])
      .slice()
      .reverse()
      .filter(item => !existingIds.has(String(item.id)))
    if (older.length) {
      messages.value = [...older, ...messages.value]
      await ensureAttachmentUrls(older)
    }
    pagination.total = Number(res?.total || pagination.total)
    await nextTick()
    if (wrap) wrap.scrollTop = wrap.scrollHeight - prevHeight + prevTop
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '加载更早的消息失败'))
  } finally {
    loadingEarlier.value = false
  }
}

// 轮询与重连时静默合并最新消息，避免打断用户阅读历史消息。
const mergeLatestConversationMessages = async () => {
  if (!props.projectId || activeFilterCount.value || viewingHistory.value || messagesLoading.value || loadingEarlier.value) return
  try {
    const res = await getProjectChatMessages(props.projectId, buildMessageParams(0, conversationPageSize), props.projectType)
    settings.enabled = !!res?.enabled
    const latestItems = Array.isArray(res?.items) ? res.items : []
    const existingById = new Map(messages.value.map(item => [String(item.id), item]))
    latestItems.forEach((item) => {
      const existing = existingById.get(String(item.id))
      if (existing) syncAcknowledgementState(existing, item)
    })
    const existingIds = new Set(messages.value.map(item => String(item.id)))
    const fresh = latestItems
      .filter(item => !existingIds.has(String(item.id)))
      .reverse()
    pagination.total = Number(res?.total || pagination.total)
    if (!fresh.length) return
    const wasAtBottom = isConversationAtBottom()
    messages.value = [...messages.value, ...fresh]
    await ensureAttachmentUrls(fresh)
    await nextTick()
    if (!props.active) return
    if (wasAtBottom) scrollConversationToBottom()
    else pendingNewCount.value += fresh.length
  } catch (error) {
    console.error('刷新沟通消息失败', error)
  }
}

const handleConversationScroll = ({ scrollTop }) => {
  if (!props.conversationMode) return
  if (scrollTop <= 2) loadEarlierMessages()
  if (isConversationAtBottom()) pendingNewCount.value = 0
  scheduleRead()
}

const handleNewMessageTipClick = async () => {
  pendingNewCount.value = 0
  await nextTick()
  scrollConversationToBottom()
}

const conversationDayKey = chatDayKey
const formatConversationDateSeparator = value => formatMessageDay(value)
const avatarText = chatAvatarText

// 时间正序 + 日期分隔线 + 同发送人连续消息合并头像与姓名。
const conversationItems = computed(() => {
  const items = []
  let previous = null
  messages.value.forEach((message) => {
    const day = conversationDayKey(message.createdAt)
    if (!previous || previous.day !== day) {
      items.push({ type: 'date', key: `date-${day}-${message.id}`, label: formatConversationDateSeparator(message.createdAt) })
    }
    const isSystem = !!message.messageType && message.messageType !== 'user'
    const sender = String(message.senderUserId || '')
    const isOwn = !isSystem && sender === currentUserId
    const groupStart = isSystem || !previous || previous.isSystem || chatGroupStart(message, previous.message)
    items.push({ type: 'message', key: `message-${message.id}`, message, isOwn, isSystem, groupStart })
    previous = { day, sender, isSystem, message }
  })
  return items
})

const toggleFilters = () => {
  conversationFiltersVisible.value = !conversationFiltersVisible.value
}

const openSearch = async () => {
  searchOpen.value = !searchOpen.value
  if (searchOpen.value) await ensureUsersLoaded()
}

const locateMessage = async (messageId) => {
  if (!messageId || !props.projectId) return
  messagesLoading.value = true
  try {
    const res = await getProjectChatMessages(props.projectId, { around: messageId, limit: 40 }, props.projectType)
    messages.value = Array.isArray(res?.items) ? res.items : []
    pagination.total = Number(res?.total || messages.value.length)
    viewingHistory.value = true
    historyHasOlder.value = !!res?.hasOlder
    pendingNewCount.value = 0
    await ensureAttachmentUrls(messages.value)
    await nextTick()
    const target = getScrollWrap()?.querySelector(`[data-message-id="${messageId}"]`)
    target?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    highlightedMessageId.value = String(messageId)
    window.clearTimeout(highlightTimer)
    highlightTimer = window.setTimeout(() => { highlightedMessageId.value = '' }, 1800)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '定位消息失败'))
  } finally {
    messagesLoading.value = false
    scheduleRead()
  }
}

const returnToLatest = async () => {
  viewingHistory.value = false
  historyHasOlder.value = false
  await conversationLoadLatest()
}

const userNameById = (userId) => {
  if(userId==='__all__')return '所有人'
  const user = userOptions.value.find(item => String(item.id) === String(userId))
  return user ? (user.full_name || user.username) : '未知用户'
}

const removeMention = (userId) => {
  composer.mentionedUserIds = composer.mentionedUserIds.filter(id => String(id) !== String(userId))
}

const resetAutomaticMentionTrigger = () => {
  automaticMentionActive.value = false
  automaticMentionTriggerIndex.value = -1
  mentionIdsAtAutomaticTrigger.value = new Set()
}

const closeMentionPopover = () => {
  mentionPopoverVisible.value = false
  resetAutomaticMentionTrigger()
}

const handleMentionPopoverHide = () => {
  resetAutomaticMentionTrigger()
}

const handleMentionEscape = () => {
  closeMentionPopover()
  nextTick(() => composerInputRef.value?.focus?.())
}

const activateAutomaticMention = async (triggerIndex) => {
  automaticMentionActive.value = true
  automaticMentionTriggerIndex.value = triggerIndex
  mentionIdsAtAutomaticTrigger.value = new Set(composer.mentionedUserIds.map(id => String(id)))
  mentionPopoverVisible.value = true
  await ensureUsersLoaded()
  await nextTick()
  mentionSelectRef.value?.focus?.()
}

// 只识别刚在光标前输入的独立 @；排除邮箱、账号等英文字符紧邻的场景。
const handleComposerInput = () => {
  if (!automaticMentionEnabled.value || composerIsComposing.value || automaticMentionActive.value) return
  nextTick(() => {
    const textarea = composerInputRef.value?.textarea
    const cursor = textarea?.selectionStart
    if (!Number.isInteger(cursor) || cursor < 1 || composer.content[cursor - 1] !== '@') return
    const previousCharacter = composer.content[cursor - 2] || ''
    if (/[A-Za-z0-9._%+-]/.test(previousCharacter)) return
    activateAutomaticMention(cursor - 1)
  })
}

const handleComposerCompositionStart = () => {
  composerIsComposing.value = true
}

const handleComposerCompositionEnd = () => {
  composerIsComposing.value = false
  handleComposerInput()
}

const handleMentionSelectionChange = (selectedUserIds) => {
  if (!automaticMentionActive.value) return
  const hasNewMention = selectedUserIds.some(id => !mentionIdsAtAutomaticTrigger.value.has(String(id)))
  if (!hasNewMention) return

  const triggerIndex = automaticMentionTriggerIndex.value
  if (triggerIndex >= 0 && composer.content[triggerIndex] === '@') {
    composer.content = `${composer.content.slice(0, triggerIndex)}${composer.content.slice(triggerIndex + 1)}`
  }
  closeMentionPopover()
  nextTick(() => {
    const textarea = composerInputRef.value?.textarea
    composerInputRef.value?.focus?.()
    const cursor = Math.min(Math.max(triggerIndex, 0), composer.content.length)
    textarea?.setSelectionRange?.(cursor, cursor)
  })
}

// Enter 发送、Shift+Enter 换行；中文输入法组词期间不触发发送。
const handleComposerKeydown = (event) => {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || composerIsComposing.value) return
  if (mentionPopoverVisible.value) {
    event.preventDefault()
    return
  }
  event.preventDefault()
  handleSend()
}

const headerReady = ref(false)
onMounted(() => { headerReady.value = true })
const { inputStyle: composerInputStyle, start: startComposerResize, resizeByKeyboard: resizeComposerByKeyboard } = useChatComposerHeight()

defineExpose({ toggleFilters, openSearch, locateMessage, locate: locateMessage })

const resetChatState = () => {
  settings.enabled = props.alwaysEnabled
  settings.canManage = false
  messages.value = []
  pagination.page = 1
  pagination.limit = 20
  pagination.total = 0
  filters.keyword = ''
  filters.senderUserId = ''
  filters.dateRange = []
  filters.favoritesOnly = false
  filterPopoverVisible.value = false
  conversationFiltersVisible.value = false
  closeMentionPopover()
  composerIsComposing.value = false
  loadingEarlier.value = false
  pendingNewCount.value = 0
  viewingHistory.value = false
  historyHasOlder.value = false
  searchOpen.value = false
  highlightedMessageId.value = ''
  clearProgressSelection(true)
  closeProgressTextMenu()
  composer.content = ''; replyToMessage.value = null
  composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
  composer.mentionedUserIds = []
  clearComposerImages()
  acknowledgementSavingIds.value = new Set()
  clearAttachmentUrls()
  clearPolling()
}

let userOptionsVersion = 0
const ensureUsersLoaded = async () => {
  if (!props.projectId) return
  const version = ++userOptionsVersion
  try {
    const data = await chatRequest(`conversations/${props.projectType}/${props.projectId}/participants`)
    if (version !== userOptionsVersion) return
    memberUserIds.value = data.members.map(user => String(user.id))
    userOptions.value = [...data.members, ...data.eligibleUsers].map(user => ({ ...user, full_name: user.name, username: user.name }))
  } catch (error) { console.error('加载会话人员失败', error) }
}

const loadSettings = async () => {
  if (!props.projectId) return
  if (props.alwaysEnabled) {
    settings.enabled = true
    settings.canManage = false
    return
  }
  settingsLoading.value = true
  try {
    const res = await getProjectChatSettings(props.projectId)
    settings.enabled = !!res?.enabled
    settings.canManage = !!res?.canManage
  } catch (error) {
    settings.enabled = false
    settings.canManage = false
    ElMessage.error(getLocalizedErrorMessage(error, '加载项目沟通配置失败'))
  } finally {
    settingsLoading.value = false
  }
}

const loadMessages = async () => {
  if (props.conversationMode) {
    await conversationLoadLatest()
    return
  }
  if (!props.projectId) {
    messages.value = []
    pagination.total = 0
    return
  }
  messagesLoading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
      keyword: filters.keyword || undefined,
      sender_user_id: filters.senderUserId || undefined,
      date_from: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[0] : undefined,
      date_to: Array.isArray(filters.dateRange) && filters.dateRange.length === 2 ? filters.dateRange[1] : undefined,
      favorites_only: filters.favoritesOnly || undefined
    }
    const res = await getProjectChatMessages(props.projectId, params, props.projectType)
    settings.enabled = !!res?.enabled
    if (typeof res?.canManage === 'boolean') settings.canManage = res.canManage
    messages.value = Array.isArray(res?.items) ? res.items : []
    if (progressSelectionMode.value) {
      const currentIds = new Set(eligibleProgressMessages.value.map(message => String(message.id)))
      selectedProgressMessageIds.value = new Set([...selectedProgressMessageIds.value].filter(id => currentIds.has(id)))
    }
    pagination.total = Number(res?.total || 0)
    if (pagination.page === 1) newerMessageNoticeShown = false
    await ensureAttachmentUrls(messages.value)
  } catch (error) {
    messages.value = []
    pagination.total = 0
    ElMessage.error(getLocalizedErrorMessage(error, '加载沟通记录失败'))
  } finally {
    messagesLoading.value = false
    scheduleRead()
  }
}

const refreshChat = async () => {
  if (!props.projectId) return
  await Promise.all([loadSettings(), ensureUsersLoaded()])
  await loadMessages()
}

const handleToggle = async (enabled) => {
  if (!props.projectId) return
  toggleLoading.value = true
  try {
    const res = await updateProjectChatSettings(props.projectId, { enabled })
    settings.enabled = !!res?.enabled
    settings.canManage = !!res?.canManage
    if (settings.enabled) {
      pagination.page = 1
      await loadMessages()
    } else {
      pagination.page = 1
      await loadMessages()
    }
    ElMessage.success(settings.enabled ? '已开启项目沟通' : '已关闭项目沟通')
  } catch (error) {
    settings.enabled = !enabled
    ElMessage.error(getLocalizedErrorMessage(error, '更新项目沟通配置失败'))
  } finally {
    toggleLoading.value = false
    setupPolling()
  }
}

const handleSearch = () => {
  clearProgressSelection(true)
  pagination.page = 1
  filterPopoverVisible.value = false
  loadMessages()
}

const handleResetSearch = () => {
  clearProgressSelection(true)
  filters.keyword = ''
  filters.senderUserId = ''
  filters.dateRange = []
  filters.favoritesOnly = false
  pagination.page = 1
  filterPopoverVisible.value = false
  loadMessages()
}

const handlePageSizeChange = () => {
  clearProgressSelection(true)
  pagination.page = 1
  loadMessages()
}

const handlePageChange = () => {
  clearProgressSelection(true)
  loadMessages()
}

const handleSend = async () => {
  if (sending.value || imagesBlocked.value || !props.projectId || (!composer.content.trim() && !pendingImages.length)) return
  const generation = composerGeneration
  sending.value = true
  try {
    const payload = props.textOnly
      ? {
          content: composer.content.trim(),
          mentionedUserIds: composer.mentionedUserIds.filter(id=>id!=='__all__'),
          mentionAll:composer.mentionedUserIds.includes('__all__'),
          ...(attachmentsEnabled.value ? { attachmentIds: pendingImages.map(item => item.attachment.id) } : {})
        }
      : {
          content: composer.content.trim(),
          contentJson: composer.contentJson,
          mentionedUserIds: composer.mentionedUserIds.filter(id=>id!=='__all__'),
          mentionAll:composer.mentionedUserIds.includes('__all__'),
          attachmentIds: pendingImages.map(item => item.attachment.id)
        }
    if(payload.mentionAll&&!payload.content.includes('@所有人')){payload.content='@所有人 '+payload.content;if(payload.contentJson)payload.contentJson={...payload.contentJson,content:[{type:'paragraph',content:[{type:'text',text:'@所有人'}]},...(payload.contentJson.content||[])]}}
    payload.replyToMessageId = replyToMessage.value?.id || null
    const fingerprint = JSON.stringify(payload)
    if (fingerprint !== sendFingerprint) { sendRequestId = newChatRequestId(); sendFingerprint = fingerprint }
    draft.persistNow()
    await createProjectChatMessage(props.projectId, { ...payload, clientMessageId: sendRequestId }, props.projectType)
    if (generation !== composerGeneration) return
    composer.content = ''; replyToMessage.value = null
    sendRequestId = ''; sendFingerprint = ''
    composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
    composer.mentionedUserIds = []
    clearComposerImages()
    closeMentionPopover()
    pagination.page = 1
    await loadMessages()
    await ensureUsersLoaded()
    ElMessage.success('消息已发送')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '发送消息失败'))
  } finally {
    sending.value = false
  }
}

const messageMentions = (message) => {
  if(message.metadata?.mentionAll || message.metadata?.mention_all)return [{mentionedUserId:'__all__',mentionedUserName:'所有人'}]
  if (Array.isArray(message?.mentions) && message.mentions.length) return message.mentions
  if (message?.mentionedUserId && message?.mentionedUserName) {
    return [{ mentionedUserId: message.mentionedUserId, mentionedUserName: message.mentionedUserName }]
  }
  return []
}

const messageAcknowledgements = message => (
  Array.isArray(message?.acknowledgements) ? message.acknowledgements : []
)

const syncAcknowledgementState = (target, source) => {
  const acknowledgements = messageAcknowledgements(source).map(item => ({ ...item }))
  target.acknowledgements = acknowledgements
  target.acknowledgementCount = acknowledgements.length
  target.isAcknowledged = acknowledgements.some(item => String(item.userId) === currentUserId)
}

const canAcknowledgeMessage = message => (
  message?.messageType === 'user'
  && String(message?.senderUserId || '') !== currentUserId
)

const shouldShowAcknowledgement = message => (
  message?.messageType === 'user'
  && (canAcknowledgeMessage(message) || messageAcknowledgements(message).length > 0)
)

const acknowledgementLabel = message => {
  const rows = messageAcknowledgements(message)
  if (!rows.length) return '收到'
  const names = rows.slice(0, 2).map(item => item.userName || '未知用户').join('、')
  return rows.length > 2 ? `${names} +${rows.length - 2}` : names
}

const acknowledgementTooltip = message => {
  const rows = messageAcknowledgements(message)
  if (!rows.length) return '标记收到'
  return rows
    .map(item => `${item.userName || '未知用户'} · ${formatDateTime(item.acknowledgedAt)}`)
    .join('；')
}

const handleAcknowledgementToggle = async (message) => {
  if (!canAcknowledgeMessage(message) || acknowledgementSavingIds.value.has(message.id)) return
  acknowledgementSavingIds.value = new Set([...acknowledgementSavingIds.value, message.id])
  const nextAcknowledged = !message.isAcknowledged
  try {
    const res = nextAcknowledged
      ? await acknowledgeProjectChatMessage(message.id)
      : await unacknowledgeProjectChatMessage(message.id)
    syncAcknowledgementState(message, res)
    ElMessage.success(message.isAcknowledged ? '已标记收到' : '已取消收到')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, nextAcknowledged ? '标记收到失败' : '取消收到失败'))
  } finally {
    const pending = new Set(acknowledgementSavingIds.value)
    pending.delete(message.id)
    acknowledgementSavingIds.value = pending
  }
}

const handleFavoriteToggle = async (message) => {
  if (!message?.id || favoriteSavingIds.value.has(message.id)) return
  favoriteSavingIds.value = new Set([...favoriteSavingIds.value, message.id])
  const nextFavorited = !message.isFavorited
  try {
    const res = nextFavorited
      ? await favoriteProjectChatMessage(message.id)
      : await unfavoriteProjectChatMessage(message.id)
    message.isFavorited = !!res?.isFavorited
    message.favoritedAt = res?.favoritedAt || null
    if (filters.favoritesOnly && !message.isFavorited) {
      await loadMessages()
    }
    ElMessage.success(message.isFavorited ? '已收藏，仅自己可见' : '已取消收藏')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, nextFavorited ? '收藏消息失败' : '取消收藏失败'))
  } finally {
    const pending = new Set(favoriteSavingIds.value)
    pending.delete(message.id)
    favoriteSavingIds.value = pending
  }
}

const handleRealtimeChatMessage = async (payload) => {
  if (
    String(payload?.projectId || '') !== String(props.projectId || '')
    || payload?.projectType !== props.projectType
    || !payload?.message?.id
  ) return
  if (messages.value.some(item => String(item.id) === String(payload.message.id))) return
  if (topics.ready) {
    try { Object.assign(payload.message, messageTopicPatch(await topicApi.message(payload.message.id))) } catch { /* 下次刷新补偿分类更新。 */ }
  }
  if (props.conversationMode) {
    if (!props.active) emit('unread')
    if (activeFilterCount.value || viewingHistory.value) {
      if (viewingHistory.value && props.active) pendingNewCount.value += 1
      return
    }
    const wasAtBottom = isConversationAtBottom()
    messages.value = [...messages.value, payload.message]
    pagination.total += 1
    await ensureAttachmentUrls([payload.message])
    await nextTick()
    if (!props.active) return
    if (wasAtBottom) scrollConversationToBottom()
    else pendingNewCount.value += 1
    return
  }
  if (pagination.page > 1) {
    if (!newerMessageNoticeShown) {
      newerMessageNoticeShown = true
      ElMessage.info('有新消息，返回第一页即可查看')
    }
    return
  }

  messages.value = [payload.message, ...messages.value].slice(0, pagination.limit)
  pagination.total += 1
  await ensureAttachmentUrls([payload.message])
  await nextTick()
  chatListRef.value?.setScrollTop?.(0)
}

const handleRealtimeChatAcknowledgement = (payload) => {
  if (
    String(payload?.projectId || '') !== String(props.projectId || '')
    || payload?.projectType !== props.projectType
    || !payload?.messageId
    || !payload?.userId
  ) return

  const message = messages.value.find(item => String(item.id) === String(payload.messageId))
  if (!message) return
  const userId = String(payload.userId)
  const next = messageAcknowledgements(message)
    .filter(item => String(item.userId) !== userId)
  if (payload.acknowledged) {
    next.push({
      userId: payload.userId,
      userName: payload.userName || '未知用户',
      acknowledgedAt: payload.acknowledgedAt || null
    })
  }
  next.sort((left, right) => {
    const leftTime = new Date(left.acknowledgedAt || 0).getTime()
    const rightTime = new Date(right.acknowledgedAt || 0).getTime()
    return leftTime - rightTime || String(left.userId).localeCompare(String(right.userId))
  })
  message.acknowledgements = next
  message.acknowledgementCount = next.length
  message.isAcknowledged = next.some(item => String(item.userId) === currentUserId)
}

const handleSocketConnected = () => {
  if (!props.active || !props.projectId) return
  if (props.conversationMode) mergeLatestConversationMessages()
  else loadMessages()
}

function localTopicChanged(event) { const row = messages.value.find(value => value.id === event.detail.id); if (row) Object.assign(row, event.detail) }
async function realtimeTopicChanged(event) {
  if (event.projectType !== props.projectType || String(event.projectId) !== String(props.projectId)) return
  const row = messages.value.find(value => value.id === event.messageId)
  if (row) { try { Object.assign(row, messageTopicPatch(await topicApi.message(row.id))) } catch { /* 后续刷新再次同步。 */ } }
}

const setupPolling = () => {
  clearPolling()
  if (!props.active || !props.projectId) return
  pollTimer = window.setInterval(() => {
    if (props.conversationMode) mergeLatestConversationMessages()
    else loadMessages()
  }, 60000)
}

const draft=useChatDraft(computed(()=>[props.projectType,props.projectId]),()=>({content:composer.content,contentJson:composer.contentJson,mentionIds:composer.mentionedUserIds,replyTo:replyToMessage.value,images:draftImages(pendingImages),sendRequestId,sendFingerprint}),data=>{
 composer.content=data.content;composer.contentJson=data.contentJson||{type:'doc',content:[{type:'paragraph'}]};composer.mentionedUserIds=data.mentionIds||[];replyToMessage.value=data.replyTo||null;sendRequestId=data.sendRequestId||'';sendFingerprint=data.sendFingerprint||''
 pendingImages.splice(0,pendingImages.length,...(data.images||[]))
 for(const item of pendingImages){getProjectChatAttachmentBlob(item.attachment.id).then(blob=>{if(pendingImages.includes(item))item.url=URL.createObjectURL(blob)}).catch(()=>{})}
})
watch(() => [props.projectId, props.projectType], async () => {
  sendFingerprint = ''; sendRequestId = ''
  resetChatState()
  if (props.projectId) {
    await refreshChat()
    setupPolling()
  }
}, { immediate: true })

watch(() => props.active, () => {
  if (!props.active) {
    // 浮窗最小化保留草稿；真正关闭时由卸载清理。
    if (!props.conversationMode) clearComposerImages()
    clearProgressSelection(true)
    closeProgressTextMenu()
    closeMentionPopover()
    composerIsComposing.value = false
  }
  setupPolling()
  if (props.active && props.projectId) {
    loadMessages()
  }
})

watch(() => settings.enabled, () => {
  setupPolling()
})

watch(() => props.canAddToProgress, canAdd => {
  if (!canAdd) {
    clearProgressSelection(true)
    closeProgressTextMenu()
  }
})

onMounted(() => {
  refreshTopics().catch(() => {})
  window.addEventListener('chat-topic-message-changed', localTopicChanged)
  unsubscribeTopicChanged = subscribe('chat_message_topic_changed', realtimeTopicChanged)
  if (props.targetMessageId) locateMessage(props.targetMessageId)
  document.addEventListener('visibilitychange', scheduleRead)
  window.addEventListener('focus', scheduleRead)
  ensureUsersLoaded()
  unsubscribeChatMessage = subscribe('chat_message', handleRealtimeChatMessage)
  unsubscribeChatAcknowledgement = subscribe('chat_message_acknowledgement', handleRealtimeChatAcknowledgement)
  unsubscribeSocketConnected = subscribe('connected', handleSocketConnected)
  ensureConnected()
})

onBeforeUnmount(() => {
  window.removeEventListener('chat-topic-message-changed', localTopicChanged)
  unsubscribeTopicChanged?.()
  window.clearTimeout(readTimer)
  document.removeEventListener('visibilitychange', scheduleRead)
  window.removeEventListener('focus', scheduleRead)
  clearComposerImages()
  unsubscribeChatMessage?.()
  unsubscribeChatAcknowledgement?.()
  unsubscribeSocketConnected?.()
  clearPolling()
  clearAttachmentUrls()
})
</script>

<style scoped>
.chat-bubble:focus-visible,.chat-message-card:focus-visible{outline:2px solid var(--el-color-primary-light-5);outline-offset:2px}
.project-chat-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-chat-panel--search-side {
  flex-direction: row;
  gap: 0;
}

.project-chat-panel__main {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
}

.project-chat-panel--conversation .project-chat-panel__main {
  gap: 0;
  height: 100%;
}

.chat-conversation-item--highlight .chat-bubble {
  outline: 2px solid var(--el-color-primary);
}

.project-chat-panel--drawer {
  min-height: 100%;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.chat-toolbar__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.chat-toolbar__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-toolbar__selection-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.chat-toolbar__hint {
  margin-top: -8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.chat-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px 16px;
  flex-wrap: wrap;
  margin-bottom: 0;
}

.chat-filter-bar :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: 0;
}

.chat-filter-bar :deep(.el-form-item__label) {
  padding-right: 8px;
}

.chat-filter-bar__range :deep(.el-date-editor) {
  width: 360px;
}

.chat-filter-bar__actions {
  flex: none;
}

.chat-filter-bar--popover {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.chat-filter-bar--popover :deep(.el-form-item) {
  margin: 0;
}

.chat-filter-bar--popover :deep(.el-form-item__label) {
  padding: 0 0 6px;
}

.chat-filter-bar--popover .chat-filter-bar__field :deep(.el-input),
.chat-filter-bar--popover .chat-filter-bar__field :deep(.el-select),
.chat-filter-bar--popover .chat-filter-bar__range :deep(.el-date-editor) {
  width: 100%;
}

.chat-filter-bar--popover .chat-filter-bar__range,
.chat-filter-bar--popover .chat-filter-bar__actions {
  grid-column: 1 / -1;
}

.chat-filter-bar--popover .chat-filter-bar__actions :deep(.el-form-item__content) {
  justify-content: flex-end;
}

.chat-list {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: #fff;
}

.chat-list__items {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.chat-message-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-fill-color-blank);
}

.chat-message-card--selectable {
  cursor: pointer;
  user-select: none;
}

.chat-message-card--selectable:hover {
  border-color: var(--el-color-primary-light-7);
}

.chat-message-card--selected {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.chat-message-card--context-active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}

.chat-message-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.chat-message-card__author {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-primary);
  flex-wrap: wrap;
}

.chat-message-card__tools {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}

.chat-message-card__favorite {
  padding: 2px;
  font-size: 17px;
}

.chat-message-card__content {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.chat-acknowledgement-row {
  display: flex;
  align-items: center;
  min-width: 0;
  margin-top: 3px;
  transition: opacity 0.15s ease;
}

.chat-conversation-item .chat-acknowledgement-row {
  margin-top: 0;
}

.chat-acknowledgement-row--own {
  justify-content: flex-end;
}

.chat-conversation-item .chat-acknowledgement-row--empty,
.chat-message-card .chat-acknowledgement-row--empty {
  opacity: 0;
}

.chat-conversation-item:hover .chat-acknowledgement-row--empty,
.chat-conversation-item:focus-within .chat-acknowledgement-row--empty,
.chat-message-card:hover .chat-acknowledgement-row--empty,
.chat-message-card:focus-within .chat-acknowledgement-row--empty {
  opacity: 1;
}

.chat-acknowledgement-chip {
  display: inline-flex;
  box-sizing: border-box;
  align-items: center;
  gap: 4px;
  max-width: min(280px, 100%);
  min-height: 20px;
  padding: 1px 6px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font: inherit;
  font-size: 11px;
  line-height: 16px;
  cursor: pointer;
}

.chat-acknowledgement-chip:hover,
.chat-acknowledgement-chip:focus-visible,
.chat-acknowledgement-chip.is-active {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  outline: none;
}

.chat-acknowledgement-chip:disabled {
  cursor: wait;
  opacity: 0.65;
}

.chat-acknowledgement-chip--readonly {
  cursor: default;
}

.chat-acknowledgement-chip__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-batch-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  box-shadow: 0 -2px 10px rgb(15 23 42 / 6%);
}

.chat-batch-action-bar__summary,
.chat-batch-action-bar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-batch-action-bar__summary {
  min-width: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-batch-action-bar__summary strong {
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.chat-batch-action-bar__summary .is-over-limit {
  color: var(--el-color-danger);
  font-weight: 600;
}

.chat-batch-action-bar__hint {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-batch-action-bar__actions {
  flex: none;
}

.handover-task-list {
  display: grid;
  gap: 6px;
  margin-top: 10px;
  padding: 10px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  font-size: 12px;
}

.handover-task-list > div {
  display: grid;
  grid-template-columns: minmax(120px, 0.8fr) minmax(160px, 1.2fr) minmax(140px, 1fr);
  gap: 10px;
}

.message-attachments {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.message-attachment {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 132px;
  color: var(--el-color-primary);
  font-size: 12px;
  text-decoration: none;
}

.message-attachment a { display: flex; flex-direction: column; gap: 4px; color: inherit; text-decoration: none; }

.message-attachment img {
  width: 132px;
  height: 96px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}

.chat-pagination {
  display: flex;
  justify-content: flex-end;
}

.chat-composer {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
  background: var(--el-fill-color-lighter);
}

.chat-composer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  font-weight: 600;
}

.chat-composer__mention {
  width: 280px;
  font-weight: 400;
}

.chat-composer__mention-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.chat-composer__mention-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}

.chat-composer__body {
  min-width: 0;
}

.chat-composer__actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.composer-attachments {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.project-chat-panel--compact {
  gap: 10px;
  font-size: 14px;
}

.project-chat-panel--compact .chat-toolbar__title {
  font-size: 14px;
}

.project-chat-panel--compact .chat-toolbar__actions {
  gap: 6px;
}

.project-chat-panel--compact .chat-filter-bar {
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
}

.project-chat-panel--compact .chat-filter-bar :deep(.el-form-item__label) {
  display: none;
}

.project-chat-panel--compact .chat-filter-bar__field :deep(.el-input) {
  width: 150px !important;
}

.project-chat-panel--compact .chat-filter-bar__field :deep(.el-select) {
  width: 130px !important;
}

.project-chat-panel--compact .chat-filter-bar__range :deep(.el-date-editor) {
  width: 250px;
}

.project-chat-panel--compact .chat-filter-bar__actions {
  margin-left: auto;
}

.project-chat-panel--compact .chat-list__items {
  gap: 8px;
  padding: 8px;
}

.project-chat-panel--compact .chat-message-card {
  padding: 10px 12px;
  border-radius: 6px;
}

.project-chat-panel--compact .chat-message-card__meta {
  margin-bottom: 5px;
}

.project-chat-panel--compact .chat-message-card__content {
  line-height: 1.5;
}

.project-chat-panel--compact .chat-composer {
  padding: 12px 14px;
  border-color: var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
}

.project-chat-panel--compact .chat-composer__header {
  margin-bottom: 10px;
  font-size: 14px;
}

.project-chat-panel--compact .chat-composer__mention {
  width: 220px;
}

.project-chat-panel--compact .chat-composer__body {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.project-chat-panel--compact .chat-composer__body > :first-child {
  min-width: 0;
  flex: 1;
}

.project-chat-panel--compact .chat-composer__actions {
  flex: none;
  margin-top: 0;
}

.project-chat-panel--conversation {
  height: 100%;
  min-height: 0;
  gap: 0;
}

.project-chat-panel--conversation .chat-toolbar {
  padding: 6px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.chat-filter-panel {
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}

.chat-conversation-wrap {
  position: relative;
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.chat-list--conversation {
  height: 100%;
  border: 0;
  border-radius: 0;
  background: var(--el-bg-color);
}

.chat-conversation {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 12px;
}

.chat-conversation__notice {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-align: center;
}

.chat-date-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-date-divider::before,
.chat-date-divider::after {
  height: 1px;
  flex: 1;
  background: var(--el-border-color-lighter);
  content: '';
}

.chat-system-message {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 4px;
}

.chat-system-message__bar {
  display: inline-flex;
  max-width: 100%;
  padding: 5px 12px;
  align-items: center;
  gap: 8px;
  border-radius: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  font-size: 12px;
  line-height: 1.5;
}

.chat-system-message__time {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
}

.chat-conversation-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.chat-conversation-item--grouped {
  margin-top: -4px;
}

.chat-conversation-item__avatar {
  width: 32px;
  flex: none;
}

.chat-avatar {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #fff;
  background: var(--el-color-primary-light-3);
  font-size: 14px;
  font-weight: 600;
}

.chat-conversation-item__main {
  display: flex;
  min-width: 0;
  max-width: calc(100% - 40px);
  flex-direction: column;
  gap: 3px;
}

.chat-conversation-item__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.chat-conversation-item__time {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
}

.chat-conversation-item__bubble-row {
  display: flex;
  align-items: flex-end;
  gap: 4px;
}

.chat-bubble {
  min-width: 0;
  padding: 8px 12px;
  border-radius: 10px;
  border-top-left-radius: 4px;
  background: var(--el-fill-color);
  color: var(--el-text-color-primary);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-bubble__text {
  white-space: pre-wrap;
}

.chat-conversation-item--own {
  justify-content: flex-end;
}

.chat-conversation-item--own .chat-conversation-item__main {
  align-items: flex-end;
}

.chat-conversation-item--own .chat-conversation-item__meta {
  flex-direction: row-reverse;
}

.chat-conversation-item--own .chat-conversation-item__bubble-row {
  flex-direction: row-reverse;
}

.chat-bubble--own {
  border-radius: 10px;
  border-top-right-radius: 4px;
  background: var(--el-color-primary-light-8);
}

.chat-conversation-item__tools {
  visibility: visible;
  flex: none;
}

.chat-new-message-tip {
  position: absolute;
  right: 16px;
  bottom: 12px;
  z-index: 2;
  padding: 6px 14px;
  border: 0;
  border-radius: 14px;
  color: #fff;
  background: var(--el-color-primary);
  box-shadow: var(--el-box-shadow-light);
  font-size: 12px;
  cursor: pointer;
}

.chat-composer--conversation {
  padding: 10px 12px;
  border: 0;
  border-top: 1px solid var(--el-border-color-lighter);
  border-radius: 0;
  background: var(--el-bg-color);
}

.chat-composer__mention-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.chat-composer__input-row {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.chat-composer__input-row > :first-child {
  flex: none;
}

.chat-composer__input-row .el-input,
.chat-composer__input-row > :nth-child(2) {
  min-width: 0;
  flex: 1;
}

.chat-composer__mention-anchor {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 1px;
  height: 34px;
  pointer-events: none;
}

@media (hover: none) {
  .chat-conversation-item .chat-acknowledgement-row--empty,
  .chat-message-card .chat-acknowledgement-row--empty {
    opacity: 1;
  }
}

@media (max-width: 720px) {
  .chat-acknowledgement-chip {
    max-width: min(220px, 100%);
  }

  .chat-batch-action-bar,
  .chat-batch-action-bar__summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .chat-batch-action-bar__actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .chat-batch-action-bar__hint {
    white-space: normal;
  }

  .chat-filter-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .chat-filter-bar--popover {
    display: grid;
    grid-template-columns: 1fr;
  }

  .chat-filter-bar--popover .chat-filter-bar__range,
  .chat-filter-bar--popover .chat-filter-bar__actions {
    grid-column: auto;
  }

  .chat-filter-bar :deep(.el-form-item) {
    display: flex;
    width: 100%;
  }

  .chat-filter-bar :deep(.el-form-item__content) {
    min-width: 0;
    flex: 1;
  }

  .chat-filter-bar__field :deep(.el-input),
  .chat-filter-bar__field :deep(.el-select),
  .chat-filter-bar__range :deep(.el-date-editor) {
    width: 100% !important;
  }

  .handover-task-list > div {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .project-chat-panel--compact .chat-filter-bar__field :deep(.el-input),
  .project-chat-panel--compact .chat-filter-bar__field :deep(.el-select),
  .project-chat-panel--compact .chat-filter-bar__range :deep(.el-date-editor) {
    width: 100% !important;
  }

  .project-chat-panel--compact .chat-filter-bar__actions {
    margin-left: 0;
  }

  .project-chat-panel--compact .chat-composer__header {
    align-items: stretch;
    flex-direction: column;
  }

  .project-chat-panel--compact .chat-composer__mention {
    width: 100%;
  }

  .chat-composer__mention-wrap {
    width: 100%;
  }

  .project-chat-panel--compact .chat-composer__body {
    align-items: stretch;
    flex-direction: column;
  }

  .project-chat-panel--compact .chat-composer__actions {
    justify-content: flex-end;
  }
}
</style>
<style scoped>
.chat-mention-jump{position:absolute;right:12px;top:48px;z-index:2}.chat-conversation-item--mentioned :deep(.chat-bubble){background:#eaf4ff;border-left:3px solid #60a5fa}
</style>

<style scoped>
.chat-visible-topic{margin-top:6px;max-width:100%;height:auto;white-space:normal;overflow-wrap:anywhere}
</style>

<style scoped>
.chat-toolbar--header{padding:0!important;border:0!important;flex:none;gap:4px}.chat-toolbar--header .chat-toolbar__title .el-tag{font-size:10px;height:20px}.chat-toolbar--header .chat-toolbar__actions{flex-wrap:nowrap}
.chat-composer--conversation{position:relative;margin:10px 12px 14px;padding:8px 10px;border:1px solid #dfe5ee;border-radius:12px;background:white;display:flex;flex-direction:column;gap:6px}.chat-composer--conversation:focus-within{border-color:var(--el-color-primary);box-shadow:0 0 0 2px var(--el-color-primary-light-9)}.chat-composer__input-row{display:flex;flex-wrap:wrap;justify-content:flex-end}.chat-composer__input-row .el-input,.chat-composer__input-row .el-textarea{flex:1 0 100%;width:100%}.chat-composer--conversation :deep(.el-textarea__inner){box-shadow:none;background:transparent;line-height:1.6;padding:6px 8px}.chat-composer-resize{position:absolute;top:-5px;left:20%;width:60%;height:8px;padding:0;border:0;background:transparent;cursor:ns-resize;touch-action:none}.chat-conversation-item__time{white-space:normal;overflow-wrap:anywhere}
</style>

<style scoped>.mention-desktop-state{display:flex;margin-top:2px}</style>

<style>.chat-mention-user-options{max-width:calc(100vw - 32px)}.chat-mention-user-options .el-select-dropdown__item{height:auto;min-height:34px;padding-top:6px;padding-bottom:6px;line-height:1.5;white-space:normal}</style>
