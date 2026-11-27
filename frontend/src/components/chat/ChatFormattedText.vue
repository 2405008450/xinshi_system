<template><span class="chat-formatted-text"><span v-for="(run,index) in runs" :key="index" :style="run.style"><mark v-if="run.highlight"><ScreenshotText :text="displayText(run.text)" :chat-message-id="message.id" :chat-kind="kind" /></mark><ScreenshotText v-else :text="displayText(run.text)" :chat-message-id="message.id" :chat-kind="kind" /></span></span></template>
<script setup>
import {computed} from 'vue'
import {formatRuns,formatText,runStyle} from '@/utils/chatTextFormat'
import {mentionParts} from '@/utils/chatMentions'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
const props=defineProps({message:{type:Object,required:true},userId:{type:String,default:()=>localStorage.getItem('user_id')||''},kind:String})
const displayText=text=>text.replace(/\[附件\]\(discussion-file:\/\/[0-9a-f-]{36}\)/gi,'')
const runs=computed(()=>{
 const message=props.message,text=message.content||'',doc=message.contentJson
 const styled=(formatText(doc)===text?formatRuns(doc):[{text,marks:[]}]);let offset=0
 const mentions=mentionParts(message,props.userId).map(part=>{const item={...part,start:offset,end:offset+part.text.length};offset=item.end;return item})
 offset=0;const result=[]
 for(const run of styled){const start=offset,end=start+run.text.length;offset=end
  for(const mention of mentions){const left=Math.max(start,mention.start),right=Math.min(end,mention.end);if(right>left)result.push({text:text.slice(left,right),style:runStyle(run.marks),highlight:mention.highlight})}
 }return result
})
</script>
<style scoped>.chat-formatted-text{white-space:pre-wrap;overflow-wrap:anywhere;color:#111827}.chat-formatted-text mark{background:#ffe49b;color:inherit}</style>
