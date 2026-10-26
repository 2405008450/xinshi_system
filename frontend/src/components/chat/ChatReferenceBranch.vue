<template>
  <div class="reference-branch">
    <article :data-reference-id="node.id" class="reference-card" :class="{'is-original':node.isOriginal,'is-current':String(node.id)===String(selectedId),'is-highlighted':String(node.id)===String(highlightedId)}">
      <header><b>{{ node.isOriginal ? '原消息' : `引用 #${node.referenceNumber}` }}</b><strong>{{ node.senderName }}</strong></header>
      <small v-if="String(node.id)===String(selectedId)" class="reference-current">当前查看的消息</small>
      <time>{{ formatBusinessDateTime(node.createdAt) }}</time>
      <button v-if="!node.isOriginal" type="button" class="reference-parent" @click="$emit('focus',node.parentId)">{{ node.parentReferenceNumber ? `引用 #${node.parentReferenceNumber}` : node.parent?.recalledAt ? '引用已撤回消息' : '引用原消息' }}</button>
      <p><ScreenshotText :text="node.content" :chat-message-id="node.id" :chat-kind="projectType" /></p>
      <el-button v-if="!node.recalledAt" link size="small" @click="$emit('locate',node.id)">{{ node.isOriginal ? '定位原消息' : '定位消息' }}</el-button>
    </article>
    <ul v-if="node.children?.length" class="reference-children">
      <li v-for="child in node.children" :key="child.id">
        <ChatReferenceBranch :node="child" :project-type="projectType" :selected-id="selectedId" :highlighted-id="highlightedId" @locate="$emit('locate',$event)" @focus="$emit('focus',$event)" />
      </li>
    </ul>
  </div>
</template>
<script setup>
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import { formatBusinessDateTime } from '@/utils/dateTime'
defineProps({node:{type:Object,required:true},projectType:String,selectedId:String,highlightedId:String})
defineEmits(['locate','focus'])
</script>
<style scoped>
.reference-branch{display:flex;flex-direction:column;align-items:center;width:max-content}
.reference-card{box-sizing:border-box;position:relative;flex:none;width:260px;padding:12px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#334155}
.reference-card.is-original{border-color:#93b8e8;background:#eff6ff}
.reference-card.is-current,.reference-card.is-highlighted{border-color:#2563eb;box-shadow:0 0 0 2px #bfdbfe}
.reference-card header{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.reference-card header b{color:#345e92;font-size:12px}.reference-card strong{font-size:13px}
.reference-current{display:block;color:#2563eb;font-size:11px;margin-top:4px}.reference-card time{display:block;color:#64748b;font-size:11px;margin-top:5px}
.reference-parent{display:block;border:0;background:transparent;color:#4b6a94;font-size:11px;padding:7px 0 0;cursor:pointer}
.reference-card p{margin:10px 0;line-height:1.65;overflow-wrap:anywhere;white-space:pre-wrap;font-size:13px}.reference-card :deep(.screenshot-preview){max-width:min(100%,320px)}
.reference-children{position:relative;display:flex;align-items:flex-start;list-style:none;margin:0;padding:0}
.reference-children::before{content:'';position:absolute;left:50%;top:0;height:14px;border-left:1.5px solid #94a3b8}
.reference-children>li{list-style:none;position:relative;display:flex;justify-content:center;margin:0;padding:28px 12px 0}
.reference-children>li::before{content:'';position:absolute;left:50%;top:14px;height:14px;border-left:1.5px solid #94a3b8}
.reference-children>li::after{content:'';position:absolute;left:0;right:0;top:14px;border-top:1.5px solid #94a3b8}
.reference-children>li:first-child::after{left:50%}.reference-children>li:last-child::after{right:50%}.reference-children>li:only-child::after{display:none}
.reference-children>li>.reference-branch>:deep(.reference-card)::before{content:'';position:absolute;left:calc(50% - 4px);top:-6px;border-left:4px solid transparent;border-right:4px solid transparent;border-top:6px solid #94a3b8}
</style>
