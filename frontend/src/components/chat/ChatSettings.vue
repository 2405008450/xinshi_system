<template>
  <section class="chat-settings" aria-label="会话设置">
    <ChatTimeDisplaySettings />
    <div class="chat-settings__annotation">
      <el-button text class="chat-settings__section" :aria-expanded="annotationExpanded" @click="annotationExpanded=!annotationExpanded">标注项目</el-button>
      <div v-if="annotationExpanded" class="chat-settings__children">
        <el-button text @click="participantsVisible=true">默认参与人设置</el-button>
      </div>
    </div>
    <div class="chat-settings__annotation"><el-button text class="chat-settings__section" :aria-expanded="businessExpanded" @click="businessExpanded=!businessExpanded">标注业务</el-button><div v-if="businessExpanded" class="chat-settings__children"><el-button text @click="defaultKind='circle'">发圈设置</el-button><el-button text @click="defaultKind='post'">发帖设置</el-button><el-button text @click="defaultKind='development'">需求设置</el-button></div></div>
    <el-config-provider :z-index="10000"><ChatDispatchDefaultsDialog :kind="defaultKind" @close="defaultKind=''" /><ChatDefaultParticipantsDialog v-model="participantsVisible" /></el-config-provider>
  </section>
</template>
<script setup>
import { ref } from 'vue'
import ChatTimeDisplaySettings from './ChatTimeDisplaySettings.vue'
import ChatDispatchDefaultsDialog from './ChatDispatchDefaultsDialog.vue'
import ChatDefaultParticipantsDialog from './ChatDefaultParticipantsDialog.vue'
const annotationExpanded=ref(false),participantsVisible=ref(false),businessExpanded=ref(false),defaultKind=ref('')
</script>
<style scoped>
.chat-settings{min-height:0;overflow-y:auto}.chat-settings__annotation{padding:0 12px 12px}.chat-settings__section{width:100%;justify-content:flex-start;font-weight:600}.chat-settings__children{padding:6px 10px}.chat-settings__children .el-button{max-width:100%;white-space:normal}
</style>
