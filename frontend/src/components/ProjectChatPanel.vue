<template>
  <div :class="['project-chat-panel', { 'project-chat-panel--drawer': drawerMode, 'project-chat-panel--compact': compact, 'project-chat-panel--conversation': conversationMode }]">
    <el-empty v-if="!projectId" description="请先选择项目" :image-size="compact ? 56 : 72" />
    <template v-else>
      <div class="chat-toolbar">
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
      </div>
      <div v-if="!alwaysEnabled" class="chat-toolbar__hint">交接与继承记录始终可见；普通留言由管理员或项目经理开启。</div>

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
        <el-scrollbar ref="chatListRef" v-loading="messagesLoading" class="chat-list chat-list--conversation" @scroll="handleConversationScroll">
          <div v-if="messages.length" class="chat-conversation">
            <div v-if="loadingEarlier" class="chat-conversation__notice">正在加载更早的消息…</div>
            <div v-else-if="!hasEarlierMessages && messages.length > conversationPageSize" class="chat-conversation__notice">已经到最早的消息了</div>
            <template v-for="item in conversationItems" :key="item.key">
              <div v-if="item.type === 'date'" class="chat-date-divider"><span>{{ item.label }}</span></div>
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
                <span class="chat-system-message__time">{{ formatDateTime(item.message.createdAt) }}</span>
              </div>
              <div
                v-else
                class="chat-conversation-item"
                :class="{ 'chat-conversation-item--own': item.isOwn, 'chat-conversation-item--grouped': !item.groupStart }"
              >
                <div v-if="!item.isOwn" class="chat-conversation-item__avatar">
                  <span v-if="item.groupStart" class="chat-avatar">{{ avatarText(item.message.senderName) }}</span>
                </div>
                <div class="chat-conversation-item__main">
                  <div v-if="item.groupStart" class="chat-conversation-item__meta">
                    <strong v-if="!item.isOwn">{{ item.message.senderName || '未知用户' }}</strong>
                    <span class="chat-conversation-item__time">{{ formatDateTime(item.message.createdAt) }}</span>
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
                    <div class="chat-bubble" :class="{ 'chat-bubble--own': item.isOwn }">
                      <div v-if="textOnly" class="chat-bubble__text">{{ item.message.content }}</div>
                      <RichTextContent v-else :document="item.message.contentJson" :fallback="item.message.content" />
                      <div v-if="item.message.attachments?.length" class="message-attachments">
                        <a
                          v-for="attachment in item.message.attachments"
                          :key="attachment.id"
                          :href="attachmentUrls[attachment.id] || undefined"
                          target="_blank"
                          rel="noopener"
                          class="message-attachment"
                        >
                          <img v-if="attachmentUrls[attachment.id]" :src="attachmentUrls[attachment.id]" :alt="attachment.originalName" />
                          <span>{{ attachment.originalName }}</span>
                        </a>
                      </div>
                    </div>
                    <div class="chat-conversation-item__tools">
                      <el-tooltip :content="item.message.isFavorited ? '取消收藏（仅自己可见）' : '收藏（仅自己可见）'" placement="top">
                        <el-button
                          link
                          :type="item.message.isFavorited ? 'warning' : 'info'"
                          :class="{ 'is-favorited': item.message.isFavorited }"
                          :loading="favoriteSavingIds.has(item.message.id)"
                          :aria-label="item.message.isFavorited ? '取消收藏' : '收藏'"
                          @click.stop="handleFavoriteToggle(item.message)"
                        >
                          <el-icon><StarFilled v-if="item.message.isFavorited" /><Star v-else /></el-icon>
                        </el-button>
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
          <el-empty v-else description="暂无沟通记录" :image-size="56" />
        </el-scrollbar>
        <button v-if="pendingNewCount" type="button" class="chat-new-message-tip" @click="handleNewMessageTipClick">
          有 {{ pendingNewCount }} 条新消息，点击查看
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
              class="chat-message-card"
              :class="{
                'chat-message-card--selected': isProgressMessageSelected(message),
                'chat-message-card--selectable': progressSelectionMode && String(message.content || '').trim(),
                'chat-message-card--context-active': progressTextMenu.visible && String(progressTextMenu.message?.id) === String(message.id)
              }"
              @click="handleProgressMessageCardClick($event, message)"
              @contextmenu="handleMessageContextMenu($event, message)"
            >
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
                  <span>{{ formatDateTime(message.createdAt) }}</span>
                  <el-tooltip :content="message.isFavorited ? '取消收藏（仅自己可见）' : '收藏（仅自己可见）'" placement="top">
                    <el-button
                      link
                      :type="message.isFavorited ? 'warning' : 'info'"
                      :loading="favoriteSavingIds.has(message.id)"
                      :aria-label="message.isFavorited ? '取消收藏' : '收藏'"
                      class="chat-message-card__favorite"
                      @click.stop="handleFavoriteToggle(message)"
                    >
                      <el-icon><StarFilled v-if="message.isFavorited" /><Star v-else /></el-icon>
                    </el-button>
                  </el-tooltip>
                </div>
              </div>
              <div
                v-if="textOnly"
                class="chat-message-card__content"
              >{{ message.content }}</div>
              <RichTextContent v-else :document="message.contentJson" :fallback="message.content" />
              <div v-if="message.metadata?.tasks?.length" class="handover-task-list">
                <div v-for="task in message.metadata.tasks" :key="task.workflowInstanceId">
                  <strong>{{ task.orderNo }}</strong>
                  <span>{{ task.taskName }}</span>
                  <span>{{ task.fromUserName }} → {{ task.toUserName }}</span>
                </div>
              </div>
              <div v-if="message.attachments?.length" class="message-attachments">
                <a
                  v-for="attachment in message.attachments"
                  :key="attachment.id"
                  :href="attachmentUrls[attachment.id] || undefined"
                  target="_blank"
                  rel="noopener"
                  class="message-attachment"
                >
                  <img v-if="attachmentUrls[attachment.id]" :src="attachmentUrls[attachment.id]" :alt="attachment.originalName" />
                  <span>{{ attachment.originalName }}</span>
                </a>
              </div>
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
          <div class="chat-composer__header">
            <span>发送消息</span>
            <div class="chat-composer__mention-wrap">
              <el-select
                v-model="composer.mentionedUserIds"
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
                <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
              </el-select>
              <span class="chat-composer__mention-count">{{ composer.mentionedUserIds.length }}/20</span>
            </div>
          </div>
          <div class="chat-composer__body">
            <el-input
              v-if="textOnly"
              v-model="composer.content"
              type="textarea"
              :autosize="compact ? { minRows: 2, maxRows: 4 } : false"
              :rows="compact ? undefined : 4"
              maxlength="10000"
              show-word-limit
              placeholder="输入项目沟通内容…"
            />
            <RichTextComposer
              v-else
              v-model="composer.contentJson"
              placeholder="输入项目沟通内容…"
              @update:plain-text="composer.content = $event"
            />
            <div class="chat-composer__actions">
              <el-button
                type="primary"
                :loading="sending"
                :disabled="!composer.content.trim() && !composer.attachments.length"
                @click="handleSend"
              >
                发送消息
              </el-button>
            </div>
          </div>
          <div v-if="!textOnly" class="composer-attachments">
            <el-upload
              :show-file-list="false"
              :http-request="handleAttachmentUpload"
              accept="image/jpeg,image/png,image/gif,image/webp"
              multiple
            >
              <el-button :loading="uploading" :disabled="composer.attachments.length >= 9">添加图片</el-button>
            </el-upload>
            <el-tag
              v-for="attachment in composer.attachments"
              :key="attachment.id"
              closable
              @close="removeComposerAttachment(attachment.id)"
            >
              {{ attachment.originalName }}
            </el-tag>
          </div>
        </div>

        <div v-if="settings.enabled && conversationMode" class="chat-composer chat-composer--conversation">
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
                <el-button
                  class="chat-composer__at"
                  :type="composer.mentionedUserIds.length ? 'primary' : 'default'"
                  plain
                  aria-label="@提醒用户"
                  title="@提醒用户"
                  @click="handleMentionButtonClick"
                >
                  @
                </el-button>
              </template>
              <div @keydown.esc.capture.stop.prevent="handleMentionEscape">
                <el-select
                  ref="mentionSelectRef"
                  v-model="composer.mentionedUserIds"
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
                  <el-option v-for="user in userOptions" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
                </el-select>
              </div>
            </el-popover>
            <el-input
              v-if="textOnly"
              ref="composerInputRef"
              v-model="composer.content"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              maxlength="10000"
              placeholder="Enter 发送，Shift+Enter 换行"
              @input="handleComposerInput"
              @compositionstart="handleComposerCompositionStart"
              @compositionend="handleComposerCompositionEnd"
              @keydown="handleComposerKeydown"
            />
            <RichTextComposer
              v-else
              v-model="composer.contentJson"
              placeholder="输入项目沟通内容…"
              @update:plain-text="composer.content = $event"
            />
            <el-button
              type="primary"
              :loading="sending"
              :disabled="sending || (!composer.content.trim() && !composer.attachments.length)"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
          <div v-if="!textOnly" class="composer-attachments">
            <el-upload
              :show-file-list="false"
              :http-request="handleAttachmentUpload"
              accept="image/jpeg,image/png,image/gif,image/webp"
              multiple
            >
              <el-button :loading="uploading" :disabled="composer.attachments.length >= 9" size="small">添加图片</el-button>
            </el-upload>
            <el-tag
              v-for="attachment in composer.attachments"
              :key="attachment.id"
              size="small"
              closable
              @close="removeComposerAttachment(attachment.id)"
            >
              {{ attachment.originalName }}
            </el-tag>
          </div>
        </div>
    </template>
    <Teleport to="body">
      <div
        v-if="canAddToProgress && progressTextMenu.visible"
        ref="progressTextMenuRef"
        class="chat-selection-menu"
        role="menu"
        :style="{ left: `${progressTextMenu.left}px`, top: `${progressTextMenu.top}px` }"
        @mousedown.stop
        @contextmenu.prevent
      >
        <button type="button" class="chat-selection-menu__item" role="menuitem" @click="handleContextMessageAddToProgress">
          <el-icon class="chat-selection-menu__icon"><CirclePlus /></el-icon>
          <span>{{ progressTextMenu.isExcerpt ? '添加选中内容为进度' : '添加为进度' }}</span>
        </button>
        <button type="button" class="chat-selection-menu__item" role="menuitem" @click="handleContextMessageCopy">
          <el-icon class="chat-selection-menu__icon"><CopyDocument /></el-icon>
          <span>{{ progressTextMenu.isExcerpt ? '复制选中内容' : '复制' }}</span>
        </button>
        <div class="chat-selection-menu__divider" role="separator"></div>
        <button type="button" class="chat-selection-menu__item" role="menuitem" @click="handleContextFavoriteToggle">
          <el-icon class="chat-selection-menu__icon">
            <StarFilled v-if="progressTextMenu.message?.isFavorited" />
            <Star v-else />
          </el-icon>
          <span>{{ progressTextMenu.message?.isFavorited ? '取消收藏' : '收藏' }}</span>
        </button>
        <button v-if="!progressSelectionMode" type="button" class="chat-selection-menu__item" role="menuitem" @click="handleContextStartMultiSelect">
          <el-icon class="chat-selection-menu__icon"><Finished /></el-icon>
          <span>多选</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script>
let projectChatUsersCache = null
let projectChatUsersRequest = null
</script>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CirclePlus, CopyDocument, Finished, Star, StarFilled } from '@element-plus/icons-vue'
import { getUsers } from '@/api/users'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import { copyTextToClipboard } from '@/utils/clipboard'
import { ensureConnected, subscribe } from '@/utils/realtimeSocket'
import {
  createProjectChatMessage,
  favoriteProjectChatMessage,
  getProjectChatAttachmentBlob,
  getProjectChatMessages,
  getProjectChatSettings,
  updateProjectChatSettings,
  unfavoriteProjectChatMessage,
  uploadProjectChatAttachment
} from '@/api/projectChat'
import RichTextComposer from '@/components/RichTextComposer.vue'
import RichTextContent from '@/components/RichTextContent.vue'

const props = defineProps({
  projectId: { type: [String, Number], default: '' },
  projectType: { type: String, default: 'translation' },
  active: { type: Boolean, default: false },
  drawerMode: { type: Boolean, default: false },
  textOnly: { type: Boolean, default: false },
  alwaysEnabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  collapsibleFilters: { type: Boolean, default: false },
  canAddToProgress: { type: Boolean, default: false },
  conversationMode: { type: Boolean, default: false }
})

const emit = defineEmits(['add-to-progress', 'unread'])

const settings = reactive({ enabled: false, canManage: false })
const settingsLoading = ref(false)
const toggleLoading = ref(false)
const messagesLoading = ref(false)
const chatListRef = ref(null)
const composerInputRef = ref(null)
const mentionSelectRef = ref(null)
const sending = ref(false)
const uploading = ref(false)
const userOptions = ref([])
const messages = ref([])
const favoriteSavingIds = ref(new Set())
const filterPopoverVisible = ref(false)
const progressSelectionMode = ref(false)
const selectedProgressMessageIds = ref(new Set())
const lastSelectedProgressMessageId = ref('')
const progressTextMenuRef = ref(null)
const progressTextMenu = reactive({ visible: false, left: 0, top: 0, message: null, text: '', isExcerpt: false })
const pagination = reactive({ page: 1, limit: 20, total: 0 })
const conversationPageSize = 20
const currentUserId = String(localStorage.getItem('user_id') || '')
const conversationFiltersVisible = ref(false)
const mentionPopoverVisible = ref(false)
const automaticMentionActive = ref(false)
const automaticMentionTriggerIndex = ref(-1)
const mentionIdsAtAutomaticTrigger = ref(new Set())
const composerIsComposing = ref(false)
const loadingEarlier = ref(false)
const pendingNewCount = ref(0)
const filters = reactive({ keyword: '', senderUserId: '', dateRange: [], favoritesOnly: false })
const composer = reactive({
  content: '',
  contentJson: { type: 'doc', content: [{ type: 'paragraph' }] },
  mentionedUserIds: [],
  attachments: []
})
const attachmentUrls = reactive({})
const attachmentObjectUrls = new Set()
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

const closeProgressTextMenu = () => {
  progressTextMenu.visible = false
  progressTextMenu.message = null
  progressTextMenu.text = ''
  progressTextMenu.isExcerpt = false
}

const handleMessageContextMenu = (event, message) => {
  if (!props.canAddToProgress || !String(message?.content || '').trim()) return
  if (event.target.closest('button, a, input, label, [role="button"], [role="checkbox"]')) return
  const selection = window.getSelection?.()
  const contentElement = event.currentTarget.querySelector('.chat-message-card__content')
  let selectedText = ''
  if (selection && !selection.isCollapsed && selection.rangeCount && contentElement) {
    const range = selection.getRangeAt(0)
    if (contentElement.contains(range.startContainer) && contentElement.contains(range.endContainer)) selectedText = selection.toString().trim()
  }
  event.preventDefault()
  event.stopPropagation()
  const menuWidth = 210
  const menuHeight = progressSelectionMode.value ? 142 : 182
  progressTextMenu.left = Math.max(8, Math.min(event.clientX, window.innerWidth - menuWidth - 8))
  progressTextMenu.top = Math.max(8, Math.min(event.clientY, window.innerHeight - menuHeight - 8))
  progressTextMenu.message = message
  progressTextMenu.text = selectedText || String(message.content).trim()
  progressTextMenu.isExcerpt = !!selectedText
  progressTextMenu.visible = true
}

const handleContextMessageAddToProgress = () => {
  if (!progressTextMenu.message || !progressTextMenu.text) return
  emit('add-to-progress', [{ ...progressTextMenu.message, content: progressTextMenu.text }])
  closeProgressTextMenu()
  window.getSelection?.()?.removeAllRanges()
}

const handleContextStartMultiSelect = () => {
  const message = progressTextMenu.message
  closeProgressTextMenu()
  if (!message) return
  progressSelectionMode.value = true
  handleProgressMessageSelection(message, true)
  window.getSelection?.()?.removeAllRanges()
}

const handleContextMessageCopy = async () => {
  const successMessage = progressTextMenu.isExcerpt ? '选中内容已复制' : '消息已复制'
  const copied = await copyTextToClipboard(progressTextMenu.text)
  if (copied) ElMessage.success(successMessage)
  else ElMessage.error('复制失败，请使用 Ctrl+C')
  closeProgressTextMenu()
}

const handleContextFavoriteToggle = async () => {
  const message = progressTextMenu.message
  closeProgressTextMenu()
  if (message) await handleFavoriteToggle(message)
}

const handleProgressTextMenuPointerDown = event => {
  if (progressTextMenu.visible && !progressTextMenuRef.value?.contains(event.target)) closeProgressTextMenu()
}

const handleProgressTextMenuKeydown = event => {
  if (event.key !== 'Escape' || !progressTextMenu.visible) return
  event.preventDefault()
  event.stopImmediatePropagation()
  closeProgressTextMenu()
}

const clearPolling = () => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const clearAttachmentUrls = () => {
  attachmentObjectUrls.forEach(url => URL.revokeObjectURL(url))
  attachmentObjectUrls.clear()
  Object.keys(attachmentUrls).forEach(key => delete attachmentUrls[key])
}

const ensureAttachmentUrls = async (items) => {
  const attachments = items.flatMap(item => item.attachments || [])
  await Promise.all(attachments.map(async (attachment) => {
    if (attachmentUrls[attachment.id]) return
    try {
      const blob = await getProjectChatAttachmentBlob(attachment.id)
      const url = URL.createObjectURL(blob)
      attachmentUrls[attachment.id] = url
      attachmentObjectUrls.add(url)
    } catch (error) {
      console.error('加载留言图片失败', error)
    }
  }))
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
  }
}

const hasEarlierMessages = computed(() => messages.value.length < pagination.total)

// 滚动到顶部加载更早消息，并保持原滚动锚点不跳动。
const loadEarlierMessages = async () => {
  if (!props.conversationMode || !hasEarlierMessages.value || loadingEarlier.value || messagesLoading.value) return
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
  if (!props.projectId || activeFilterCount.value || messagesLoading.value || loadingEarlier.value) return
  try {
    const res = await getProjectChatMessages(props.projectId, buildMessageParams(0, conversationPageSize), props.projectType)
    settings.enabled = !!res?.enabled
    const existingIds = new Set(messages.value.map(item => String(item.id)))
    const fresh = (Array.isArray(res?.items) ? res.items : [])
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
}

const handleNewMessageTipClick = async () => {
  pendingNewCount.value = 0
  await nextTick()
  scrollConversationToBottom()
}

const conversationDayKey = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

const formatConversationDateSeparator = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const today = new Date()
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1)
  if (conversationDayKey(date) === conversationDayKey(today)) return '今天'
  if (conversationDayKey(date) === conversationDayKey(yesterday)) return '昨天'
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

const avatarText = (name) => String(name || '?').trim().slice(0, 1) || '?'

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
    const groupStart = isSystem || !previous || previous.isSystem || previous.sender !== sender || previous.day !== day
    items.push({ type: 'message', key: `message-${message.id}`, message, isOwn, isSystem, groupStart })
    previous = { day, sender, isSystem }
  })
  return items
})

const toggleFilters = () => {
  conversationFiltersVisible.value = !conversationFiltersVisible.value
}

const userNameById = (userId) => {
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

const handleMentionButtonClick = () => {
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
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  if (mentionPopoverVisible.value) {
    event.preventDefault()
    return
  }
  event.preventDefault()
  handleSend()
}

defineExpose({ toggleFilters })

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
  clearProgressSelection(true)
  closeProgressTextMenu()
  composer.content = ''
  composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
  composer.mentionedUserIds = []
  composer.attachments = []
  clearAttachmentUrls()
  clearPolling()
}

const ensureUsersLoaded = async () => {
  if (userOptions.value.length) return
  try {
    if (projectChatUsersCache) {
      userOptions.value = projectChatUsersCache
      return
    }
    if (!projectChatUsersRequest) {
      projectChatUsersRequest = getUsers({ skip: 0, limit: 500 })
        .then(res => {
          projectChatUsersCache = Array.isArray(res)
            ? res.filter(user => user.isActive !== false && user.is_active !== false)
            : []
          return projectChatUsersCache
        })
        .catch(error => {
          projectChatUsersRequest = null
          throw error
        })
    }
    userOptions.value = await projectChatUsersRequest
  } catch (error) {
    console.error('加载用户失败', error)
  }
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
  if (!props.projectId || (!composer.content.trim() && !composer.attachments.length)) return
  sending.value = true
  try {
    const payload = props.textOnly
      ? {
          content: composer.content.trim(),
          mentionedUserIds: composer.mentionedUserIds
        }
      : {
          content: composer.content.trim(),
          contentJson: composer.contentJson,
          mentionedUserIds: composer.mentionedUserIds,
          attachmentIds: composer.attachments.map(item => item.id)
        }
    await createProjectChatMessage(props.projectId, payload, props.projectType)
    composer.content = ''
    composer.contentJson = { type: 'doc', content: [{ type: 'paragraph' }] }
    composer.mentionedUserIds = []
    composer.attachments = []
    closeMentionPopover()
    pagination.page = 1
    await loadMessages()
    ElMessage.success('消息已发送')
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '发送消息失败'))
  } finally {
    sending.value = false
  }
}

const messageMentions = (message) => {
  if (Array.isArray(message?.mentions) && message.mentions.length) return message.mentions
  if (message?.mentionedUserId && message?.mentionedUserName) {
    return [{ mentionedUserId: message.mentionedUserId, mentionedUserName: message.mentionedUserName }]
  }
  return []
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

const handleAttachmentUpload = async ({ file }) => {
  if (composer.attachments.length >= 9) {
    ElMessage.warning('每条留言最多添加 9 张图片')
    return
  }
  uploading.value = true
  try {
    const attachment = await uploadProjectChatAttachment(file)
    composer.attachments.push(attachment)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '图片上传失败'))
  } finally {
    uploading.value = false
  }
}

const removeComposerAttachment = (attachmentId) => {
  composer.attachments = composer.attachments.filter(item => item.id !== attachmentId)
}

const handleRealtimeChatMessage = async (payload) => {
  if (
    String(payload?.projectId || '') !== String(props.projectId || '')
    || payload?.projectType !== props.projectType
    || !payload?.message?.id
  ) return
  if (messages.value.some(item => String(item.id) === String(payload.message.id))) return
  if (props.conversationMode) {
    if (!props.active) emit('unread')
    if (activeFilterCount.value) return
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

const handleSocketConnected = () => {
  if (!props.active || !props.projectId) return
  if (props.conversationMode) mergeLatestConversationMessages()
  else loadMessages()
}

const setupPolling = () => {
  clearPolling()
  if (!props.active || !props.projectId) return
  pollTimer = window.setInterval(() => {
    if (props.conversationMode) mergeLatestConversationMessages()
    else loadMessages()
  }, 60000)
}

watch(() => [props.projectId, props.projectType], async () => {
  resetChatState()
  if (props.projectId) {
    await refreshChat()
    setupPolling()
  }
}, { immediate: true })

watch(() => props.active, () => {
  if (!props.active) {
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
  ensureUsersLoaded()
  unsubscribeChatMessage = subscribe('chat_message', handleRealtimeChatMessage)
  unsubscribeSocketConnected = subscribe('connected', handleSocketConnected)
  ensureConnected()
  document.addEventListener('mousedown', handleProgressTextMenuPointerDown)
  document.addEventListener('scroll', closeProgressTextMenu, true)
  window.addEventListener('resize', closeProgressTextMenu)
  window.addEventListener('keydown', handleProgressTextMenuKeydown, true)
})

onBeforeUnmount(() => {
  unsubscribeChatMessage?.()
  unsubscribeSocketConnected?.()
  clearPolling()
  clearAttachmentUrls()
  document.removeEventListener('mousedown', handleProgressTextMenuPointerDown)
  document.removeEventListener('scroll', closeProgressTextMenu, true)
  window.removeEventListener('resize', closeProgressTextMenu)
  window.removeEventListener('keydown', handleProgressTextMenuKeydown, true)
})
</script>

<style scoped>
.project-chat-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.chat-selection-menu {
  position: fixed;
  z-index: 5000;
  display: flex;
  min-width: 210px;
  flex-direction: column;
  padding: 6px 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color-overlay);
  box-shadow: var(--el-box-shadow-light);
}

.chat-selection-menu__item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 40px;
  padding: 8px 16px;
  border: 0;
  color: var(--el-text-color-regular);
  background: transparent;
  font: inherit;
  line-height: 1.3;
  text-align: left;
  cursor: pointer;
}

.chat-selection-menu__item:hover,
.chat-selection-menu__item:focus-visible {
  outline: none;
  background: var(--el-fill-color-light);
}

.chat-selection-menu__icon {
  width: 18px;
  font-size: 17px;
  color: var(--el-text-color-secondary);
  flex: none;
}

.chat-selection-menu__divider {
  height: 1px;
  margin: 5px 12px;
  background: var(--el-border-color-lighter);
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
  visibility: hidden;
  flex: none;
}

.chat-conversation-item:hover .chat-conversation-item__tools,
.chat-conversation-item__tools:has(.is-favorited) {
  visibility: visible;
}

.chat-conversation-item__tools .el-button {
  padding: 2px;
  font-size: 15px;
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

.chat-composer__at {
  width: 34px;
  height: 34px;
  padding: 0;
  font-size: 15px;
  font-weight: 600;
}

@media (max-width: 720px) {
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
