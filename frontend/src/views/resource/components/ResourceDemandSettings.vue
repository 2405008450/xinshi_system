<template>
  <DraggableFormDialog v-model="visible" title="需求发送设置" width="min(560px,calc(100vw - 32px))" append-to-body>
    <p>口译、标注项目共用默认接收人；发送需求时可临时调整。</p>
    <div class="demand-settings"><el-button v-for="kind in kinds" :key="kind" @click="activeKind=kind">{{ resourceDispatchLabels[kind] }}设置</el-button></div>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
    <ChatDispatchDefaultsDialog :kind="activeKind" @close="activeKind=''" />
  </DraggableFormDialog>
</template>
<script setup>
import {ref} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ChatDispatchDefaultsDialog from '@/components/chat/ChatDispatchDefaultsDialog.vue'
import {resourceDispatchLabels} from '@/utils/resourceRequestDispatchKinds'
const visible=defineModel({type:Boolean,default:false}),activeKind=ref('')
const kinds=['circle','wechat_public','xiaohongshu','post','development']
</script>
<style scoped>.demand-settings{display:flex;flex-direction:column;gap:12px}.demand-settings .el-button{margin:0}p{color:#64748b;line-height:1.7}</style>
