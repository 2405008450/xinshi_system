<template>
    <div ref="composer" class="group-composer" :style="composerStyle" @paste.capture="paste">
      <button type="button" class="chat-composer-resize" aria-label="调整输入区高度" title="拖动调整输入区高度" @pointerdown="start" @keydown="resizeByKeyboard" />
      <div v-if="replyTo" class="group-compose-reply">回复 {{ replyTo.senderName }}：{{ screenshotPreview(replyTo.content) || '[附件]' }}<el-button link :disabled="sending || !!retryPayload" @click="cancelQuote">取消引用</el-button></div>
      <div class="group-compose-tools">
        <el-button text size="small" aria-label="提及用户" title="提及用户" :disabled="sending || !!retryPayload" @click="insertMention">@</el-button>
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" accept=".jpg,.jpeg,.png,.gif,.webp" :on-change="chooseFile"><el-button text size="small" :icon="Picture" :disabled="sending || !!retryPayload" aria-label="发送图片" title="发送图片：单张10MB，聊天截图保留30天" /></el-upload>
        <el-upload :show-file-list="false" :auto-upload="false" multiple :disabled="sending || !!retryPayload" :accept="chatFileAccept" :on-change="chooseFile"><el-button text size="small" :icon="Paperclip" :disabled="sending || !!retryPayload" aria-label="发送文件" :title="`发送文件：${chatFileHint}`" /></el-upload>
      </div>
      <div v-if="files.length" class="group-file-queue"><div v-for="file in files" :key="file.key">{{ file.file.name }} · {{ file.status === 'uploading' ? `上传中 ${file.progress || 0}%`  : file.status === 'failed' ? '上传失败' : '待发送' }}<el-button v-if="file.status==='failed'" link @click="uploadFile(file)">重试</el-button><el-button link :disabled="sending || !!retryPayload" @click="removeFile(file)">移除</el-button><span v-if="file.error" class="group-error">{{ file.error }}</span></div></div>
      <div v-if="pendingImages.length || legacyImageIds.length" class="group-image-queue" aria-label="待发送图片">
        <div v-for="image in pendingImages" :key="image.key" class="group-image-card" :aria-label="image.file.name">
          <img v-if="image.url" :src="image.url" :alt="image.file.name" />
          <ScreenshotText v-else :text="screenshotValue('', [image.attachment.reference || image.attachment.id])" :show-text="false" />
          <div class="group-image-status" :title="image.error || image.file.name" :role="image.status === 'failed' ? 'alert' : undefined">
            <span>{{ image.status === 'uploading' ? '上传中…' : image.status === 'failed' ? image.error : '待发送' }}</span>
            <button v-if="image.status === 'failed'" type="button" :disabled="sending || !!retryPayload" @click="imageQueue.retry(image)">重试</button>
          </div>
          <button type="button" class="group-image-remove" aria-label="移除图片" :disabled="sending || !!retryPayload" @click="imageQueue.remove(image.key)">×</button>
        </div>
        <div v-for="id in legacyImageIds" :key="id" class="group-image-card">
          <ScreenshotText :text="screenshotValue('', [id])" :show-text="false" />
          <button type="button" class="group-image-remove" aria-label="移除图片" :disabled="sending || !!retryPayload" @click="removeLegacyImage(id)">×</button>
        </div>
      </div>
      <BaseInput ref="input" class="group-compose-input" v-model="plainContent" type="textarea" :rows="3" :input-style="inputStyle" resize="none" maxlength="10000" :disabled="sending || !!retryPayload" placeholder="输入消息…" :aria-expanded="mentionOpen" aria-autocomplete="list" :aria-controls="mentionOpen ? mentionListId : undefined" :aria-activedescendant="mentionOpen && mentionCandidates.length ? `${mentionListId}-${mentionIndex}` : undefined" @input="onInput" @click="onInput" @keyup.left="onInput" @keyup.right="onInput" @scroll.capture="closeMention" @blur="onMentionBlur" @keydown="onKeydown" @compositionstart="composing=true; closeMention()" @compositionend="finishComposition" />
      <div v-if="mentionOpen" :id="mentionListId" ref="mentionMenu" class="group-mention-menu" :style="mentionStyle" role="listbox" aria-label="选择提及用户" @mousedown="keepMentionFocus">
        <div class="group-mention-heading">提及用户<span>↑↓ 选择 · Enter 确认</span></div>
        <el-input v-model="mentionQuery" class="group-mention-search" clearable placeholder="搜索要 @ 的人员" aria-label="搜索要提及的人员" @input="mentionIndex = 0" @blur="onMentionBlur" @keydown="onKeydown" />
        <div class="group-mention-options">
          <template v-for="(user, index) in mentionCandidates" :key="user.id">
            <div v-if="!index || (user.mentionSection || user.outside) !== (mentionCandidates[index - 1].mentionSection || mentionCandidates[index - 1].outside)" class="group-mention-section" :class="{ 'is-outside': user.outside }">{{ user.mentionSection || (user.outside ? '未参与人员 · 发送后自动加入' : '群组参与人') }}</div>
            <button :id="`${mentionListId}-${index}`" type="button" role="option" :aria-selected="index === mentionIndex" :class="{ 'is-active': index === mentionIndex, 'is-outside': user.outside }" @mouseenter="mentionIndex=index" @click="selectMention(user)"><span class="group-mention-avatar">{{ user.name.slice(0, 1) }}</span><span class="group-mention-person"><span>{{ user.name }}</span><ChatDesktopPresence v-if="!user.all" :online="desktopPresence[user.id]" :work-status="workStatuses[user.id]" :loading="desktopPresenceLoading" /></span><small v-if="user.outside">邀请入群</small></button>
          </template>
          <div v-if="!mentionCandidates.length" class="group-mention-empty">没有匹配的用户</div>
        </div>
      </div>
      <small v-if="contentTooLong" class="group-error" role="alert">文字与图片引用合计超过10000字，请减少文字或图片后发送</small>
      <small v-if="draft.error.value" role="alert">{{draft.error.value}}</small>
      <div class="group-compose-footer"><el-button v-if="retryPayload" size="small" @click="cancelRetry">继续编辑</el-button><el-button type="primary" size="small" :loading="sending" :disabled="!canSend" title="Enter 发送，Shift+Enter 换行" @click="send">{{ retryPayload ? '发送失败，重试' : '发送' }}</el-button></div>
      <div v-if="sendError" class="group-error" role="alert">{{ sendError }}</div>
    </div>
</template>
<script setup>
import { chatFileAccept, chatFileHint } from '@/utils/chatFileTypes'
import { screenshotIds, screenshotText, screenshotValue, screenshotPreview } from '@/utils/screenshotReferences'
import { computed, inject, nextTick } from 'vue'
import { ElInput as BaseInput } from 'element-plus'
import 'element-plus/es/components/input/style/css'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import ChatDesktopPresence from './ChatDesktopPresence.vue'
import { useDesktopPresence } from '@/composables/useDesktopPresence'
import { Paperclip, Picture } from '@element-plus/icons-vue'
import { useChatComposerHeight } from '@/composables/useChatComposerHeight'
const { composerStyle, inputStyle, start, resizeByKeyboard } = useChatComposerHeight()
const { contentTooLong, pendingImages, imageQueue, draft, props, composer, replyTo, cancelQuote, sending, retryPayload, files, chooseFile, uploadFile, removeFile, input, content, mentionOpen, mentionListId, mentionQuery, mentionCandidates, mentionIndex, onInput, closeMention, onKeydown, composing, finishComposition, paste, mentionMenu, mentionStyle, selectMention, cancelRetry, canSend, send, sendError } = inject('chatController')
// 仅在发送时组合截图引用，文本框始终只编辑可见文字，兼容历史草稿。
const legacyImageIds = computed(() => screenshotIds(content.value))
const plainContent = computed({ get: () => screenshotText(content.value), set: value => { content.value = screenshotValue(value, legacyImageIds.value) } })
function removeLegacyImage(id) { content.value = screenshotValue(plainContent.value, legacyImageIds.value.filter(value => value !== id)) }
const { statuses: desktopPresence, workStatuses, loading: desktopPresenceLoading } = useDesktopPresence(computed(() => mentionCandidates.value.filter(user=>!user.all).map(user => user.id)), computed(() => props.active && mentionOpen.value))
function keepMentionFocus(event) {
  // 搜索框需要获得焦点；候选按钮保留输入光标，确保选择时替换正确的 @ 文本。
  if (!event.target.closest('input')) event.preventDefault()
}
function onMentionBlur(event) {
  if (!mentionMenu.value?.contains(event.relatedTarget)) closeMention()
}
async function insertMention() {
  const textarea = input.value?.textarea
  const cursor = textarea?.selectionStart ?? content.value.length, end = textarea?.selectionEnd ?? cursor
  const text = `${cursor && !/\s$/.test(content.value.slice(0, cursor)) ? ' ' : ''}@`
  content.value = content.value.slice(0, cursor) + text + content.value.slice(end)
  await nextTick(); input.value?.focus(); textarea?.setSelectionRange(cursor + text.length, cursor + text.length); onInput()
}
</script>
<style scoped src="./chatConversation.css" />
<style scoped>.group-composer{margin:10px 12px 14px;border:1px solid var(--chat-border,#e2e8f0);border-radius:12px;padding:8px 10px;box-shadow:0 2px 6px #0f172a03}.group-compose-tools .el-icon{font-size:var(--chat-icon-size,16px)}.group-composer:focus-within{border-color:var(--el-color-primary);box-shadow:0 0 0 2px var(--el-color-primary-light-9)}.group-compose-tools{flex-wrap:wrap;gap:6px}.group-compose-footer{justify-content:flex-end;gap:10px}.chat-composer-resize{position:absolute;top:-5px;left:20%;width:60%;height:8px;padding:0;border:0;background:transparent;cursor:ns-resize;touch-action:none}.chat-composer-resize:focus-visible{outline:2px solid var(--el-color-primary)}.group-mention-search{flex-shrink:0;margin-bottom:5px}.group-mention-section{position:sticky;top:0;padding:7px;background:#eff6ff;color:#1d4ed8;font-size:11px;font-weight:600;border-bottom:1px solid #dbeafe}.group-mention-section.is-outside{background:#fff7ed;color:#9a3412;border-top:2px solid #fed7aa;border-bottom-color:#ffedd5}.group-mention-options button small{margin-left:auto;flex:none;color:#9a3412;font-size:10px}
</style>
<style scoped>
/* 手机端输入区仿微信：输入框与发送按钮同一行，快捷工具收在下方一行，贴底固定。 */
@media (max-width: 640px) {
  .group-composer{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:'reply reply' 'queue queue' 'images images' 'input send' 'tools tools' 'error error';align-items:end;gap:6px 8px;margin:0;padding:8px 10px calc(8px + env(safe-area-inset-bottom));border:0;border-top:1px solid var(--chat-border,#e2e8f0);border-radius:0;background:var(--chat-sidebar-bg,#f8fafc);box-shadow:none}
  .group-composer:focus-within{border-color:var(--chat-border,#e2e8f0);box-shadow:none}
  .chat-composer-resize{display:none}
  .group-compose-reply{grid-area:reply;margin:0}
  .group-file-queue{grid-area:queue}
  .group-image-queue{grid-area:images;height:80px}
  .group-image-card{width:96px}
  .group-composer > .group-compose-input{grid-area:input;min-width:0}
  .group-composer :deep(.el-textarea__inner){padding:9px 10px;border-radius:6px;background:#fff;font-size:16px}
  .group-compose-footer{grid-area:send;margin:0}
  .group-compose-footer .el-button{height:40px;padding:0 16px}
  .group-compose-tools{grid-area:tools;margin:0;flex-wrap:nowrap;gap:2px}
  .group-compose-tools .el-button{width:36px;height:32px;padding:0;font-size:18px}
  .group-error,.group-composer > small{grid-area:error}
}
</style>


<style scoped>
/* 高度只由公共变量控制，覆盖 Element Plus 每次输入重新计算的 min-height。 */
.group-compose-input :deep(.el-textarea__inner){height:min(var(--chat-composer-height,80px),25dvh)!important;min-height:0!important;max-height:min(var(--chat-composer-height,80px),25dvh)!important;overflow-y:auto;field-sizing:fixed}
.group-image-queue{display:flex;flex-wrap:nowrap;gap:8px;height:100px;box-sizing:border-box;padding:4px 0;overflow-x:auto;overflow-y:hidden;flex-shrink:0}
.group-image-card{position:relative;flex:0 0 120px;height:100%;min-width:0;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;box-sizing:border-box;background:#f8fafc}
.group-image-card>img{display:block;width:100%;height:100%;object-fit:contain}
.group-image-status{position:absolute;bottom:0;left:0;right:0;display:flex;gap:4px;background:#ffffffed;padding:2px 4px;font-size:11px;line-height:18px;min-width:0}
.group-image-status span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.group-image-status button{border:0;background:transparent;color:var(--el-color-primary);cursor:pointer;flex:none;padding:0}
.group-image-remove{position:absolute;right:2px;top:2px;width:22px;height:22px;padding:0;border:1px solid #cbd5e1;border-radius:4px;background:white;cursor:pointer}
.group-image-remove:disabled{cursor:not-allowed}
.group-image-card :deep(.screenshot-text),.group-image-card :deep(.screenshot-previews),.group-image-card :deep(.screenshot-preview),.group-image-card :deep(.el-image){width:100%;height:100%;min-width:0;max-width:100%;margin:0}
.group-image-card :deep(.screenshot-previews){overflow:hidden}
@media(max-width:640px){.group-image-queue{height:80px}.group-image-card{flex-basis:96px}}
</style>
<style scoped>
.group-mention-person{display:flex;flex:1;min-width:0;flex-direction:column;align-items:flex-start;gap:3px}
.group-mention-avatar{flex-shrink:0}
</style>
