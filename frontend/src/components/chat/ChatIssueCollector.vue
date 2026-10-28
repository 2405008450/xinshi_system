<template><DevelopmentIssueEditor ref="editorRef" @saved="saved" /></template>
<script setup>
import { nextTick, ref, watch } from 'vue'
import { useResourceIssues } from '@/composables/useResourceIssues'
import DevelopmentIssueEditor from '@/views/resource/components/DevelopmentIssueEditor.vue'
const {collector,refreshIssueAccess}=useResourceIssues(), editorRef=ref()
watch(()=>[collector.visible,collector.messageId,collector.category,collector.discussionRoomId],async()=>{if(!collector.visible)return;await nextTick();const {messageId,category,discussionRoomId}=collector;collector.visible=false;await editorRef.value.open(null,messageId,category,discussionRoomId)},{immediate:true})
function saved(){window.dispatchEvent(new CustomEvent('resource-issue-saved'));refreshIssueAccess(true).catch(()=>{})}
</script>
