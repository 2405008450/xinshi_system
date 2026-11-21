<template>
  <div class="reference-branch">
    <article
      :data-reference-id="node.id"
      class="reference-card"
      :class="{
        'is-original': node.isOriginal,
        'is-own': isOwn,
        'is-mentioned': isMentioned,
        'is-recalled': !!node.recalledAt,
        'is-current': String(node.id) === String(selectedId),
        'is-highlighted': String(node.id) === String(highlightedId),
      }"
    >
      <header>
        <b class="reference-badge" :class="{ 'is-original': node.isOriginal }">{{ node.isOriginal ? '原消息' : `引用 #${node.referenceNumber}` }}</b>
        <strong>{{ node.senderName }}</strong>
        <small v-if="String(node.id) === String(selectedId)" class="reference-current">当前查看</small>
      </header>
      <time>{{ formatBusinessDateTime(node.createdAt) }}</time>
      <div v-if="extraMentions.length" class="reference-mentions" aria-label="消息提及人员">
        <span v-for="item in extraMentions" :key="item.id" :class="{ 'is-highlight': item.highlight }">{{ item.label }}</span>
      </div>
      <button v-if="!node.isOriginal" type="button" class="reference-parent" @click="$emit('focus', node.parentId)">{{ node.parentReferenceNumber ? `引用 #${node.parentReferenceNumber}` : node.parent?.recalledAt ? '引用已撤回消息' : '引用原消息' }}</button>
      <p class="reference-content">
        <template v-for="(part, partIndex) in contentParts" :key="partIndex">
          <span :class="{ 'reference-mention-highlight': part.highlight }">
            <template v-for="(seg, segIndex) in splitUrgentText(part.text)" :key="segIndex">
              <span v-if="seg.urgent" class="reference-urgent-badge">急</span>
              <ScreenshotText v-else :text="seg.text" :chat-message-id="node.id" :chat-kind="projectType" />
            </template>
          </span>
        </template>
      </p>
      <el-button v-if="!node.recalledAt" link size="small" class="reference-locate" @click="$emit('locate', node.id)">{{ node.isOriginal ? '定位原消息' : '定位消息' }}</el-button>
    </article>
    <ul v-if="node.children?.length" class="reference-children">
      <li v-for="child in node.children" :key="child.id">
        <ChatReferenceBranch :node="child" :project-type="projectType" :current-user-id="currentUserId" :selected-id="selectedId" :highlighted-id="highlightedId" @locate="$emit('locate', $event)" @focus="$emit('focus', $event)" />
      </li>
    </ul>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { mentionParts, undisplayedMentions } from '@/utils/chatMentions'
const props = defineProps({ node: { type: Object, required: true }, projectType: String, currentUserId: { type: String, default: '' }, selectedId: String, highlightedId: String })
defineEmits(['locate', 'focus'])
const isOwn = computed(() => !props.node.recalledAt && !!props.currentUserId && String(props.node.senderUserId ?? props.node.sender_user_id ?? '') === String(props.currentUserId))
const isMentioned = computed(() => !props.node.recalledAt && !!props.currentUserId && (props.node.mentions || []).some(item => String(item.mentionedUserId ?? item.mentioned_user_id ?? '') === String(props.currentUserId)))
const extraMentions = computed(() => undisplayedMentions(props.node, props.currentUserId))
const contentParts = computed(() => mentionParts(props.node, props.currentUserId))
const splitUrgentText = text => {
  const value = String(text || '')
  if (!value.includes('**急**')) return [{ text: value }]
  return value.split(/(\*\*急\*\*)/).filter(Boolean).map(seg => seg === '**急**' ? { urgent: true } : { text: seg })
}
</script>
<style scoped>
.reference-branch{display:flex;flex-direction:column;align-items:center;width:max-content}
.reference-card{box-sizing:border-box;position:relative;flex:none;width:268px;padding:12px 13px;border:1px solid var(--chat-bubble-border,#e5eaf0);border-radius:10px;background:var(--chat-bubble-bg,#ffffff);box-shadow:var(--chat-bubble-shadow,0 1px 2px rgba(15,23,42,.04));color:var(--chat-text,#1e293b);transition:border-color .14s ease,box-shadow .14s ease}
.reference-card.is-own{background:var(--chat-bubble-own-bg,#e3ecf6);border-color:var(--chat-bubble-own-border,#ccd9e8)}
.reference-card.is-mentioned{background:var(--chat-bubble-mention-bg,#fef9ec);border-color:#f3d99b;border-left:3px solid var(--chat-bubble-mention-accent,#d97706)}
.reference-card.is-recalled{background:#f8fafc;border-style:dashed;border-color:#cbd5e1;color:#94a3b8}
.reference-card.is-current,.reference-card.is-highlighted{border-color:#334155;box-shadow:0 0 0 2px rgba(51,65,85,.18),0 4px 12px rgba(15,23,42,.08)}
.reference-card.is-mentioned.is-current,.reference-card.is-mentioned.is-highlighted{border-left-color:var(--chat-bubble-mention-accent,#d97706)}
.reference-card header{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.reference-badge{display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;background:#eef2f7;color:#475569;font-size:11px;font-weight:600;line-height:1.5}
.reference-badge.is-original{background:#e2e8f0;color:#1e293b}
.reference-card.is-own .reference-badge{background:rgba(255,255,255,.72);color:#334155}
.reference-card.is-mentioned .reference-badge{background:#fef3c7;color:#92400e}
.reference-card strong{font-size:13px;font-weight:600;color:#1e293b}
.reference-current{margin-left:auto;padding:1px 6px;border-radius:10px;background:#334155;color:#fff;font-size:10.5px;font-weight:500;line-height:1.5}
.reference-card time{display:block;color:#94a3b8;font-size:11px;margin-top:4px;font-variant-numeric:tabular-nums}
.reference-mentions{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;font-size:11.5px}
.reference-mentions span{padding:1px 6px;border-radius:10px;background:#e8eef6;color:#334155;font-weight:500}
.reference-mentions span.is-highlight{background:#fef3c7;color:#92400e}
.reference-parent{display:inline-flex;align-items:center;border:0;border-radius:4px;background:rgba(100,116,139,.1);color:#475569;font-size:11px;padding:2px 7px;margin-top:7px;cursor:pointer;transition:background-color .12s ease,color .12s ease}
.reference-parent:hover{background:rgba(51,65,85,.16);color:#1e293b}
.reference-content{margin:8px 0 6px;line-height:1.65;overflow-wrap:anywhere;white-space:pre-wrap;font-size:13px;color:inherit;user-select:text}
.reference-mention-highlight{background:#fef3c7;color:#92400e;border-radius:4px;padding:0 3px;font-weight:500}
.reference-urgent-badge{display:inline-flex;align-items:center;justify-content:center;margin-right:5px;padding:0 5px;height:18px;border-radius:4px;background:#fee2e2;color:#dc2626;font-size:11px;font-weight:600;line-height:18px;vertical-align:1px}
.reference-card :deep(.screenshot-preview){max-width:min(100%,320px)}
.reference-locate{padding-left:0;font-size:12px}
.reference-children{position:relative;display:flex;align-items:flex-start;list-style:none;margin:0;padding:0}
.reference-children::before{content:'';position:absolute;left:50%;top:0;height:14px;border-left:1.5px solid #94a3b8}
.reference-children>li{list-style:none;position:relative;display:flex;justify-content:center;margin:0;padding:28px 12px 0}
.reference-children>li::before{content:'';position:absolute;left:50%;top:14px;height:14px;border-left:1.5px solid #94a3b8}
.reference-children>li::after{content:'';position:absolute;left:0;right:0;top:14px;border-top:1.5px solid #94a3b8}
.reference-children>li:first-child::after{left:50%}.reference-children>li:last-child::after{right:50%}.reference-children>li:only-child::after{display:none}
.reference-children>li>.reference-branch>:deep(.reference-card)::before{content:'';position:absolute;left:calc(50% - 4px);top:-6px;border-left:4px solid transparent;border-right:4px solid transparent;border-top:6px solid #94a3b8}
</style>
