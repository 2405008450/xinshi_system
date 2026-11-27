<template>
  <el-button class="chat-help-entry" :class="{'is-compact':compact}" text :icon="QuestionFilled" aria-label="会话帮助" title="会话帮助：目录、收藏、消息、通知及协作" @mousedown.stop @click.stop="visible=true"><span>会话帮助</span></el-button>
  <ChatNavigationHelp v-if="visible" v-model="visible" />
</template>
<script setup>
import {defineAsyncComponent,ref} from 'vue'
import {QuestionFilled} from '@element-plus/icons-vue'
const visible=ref(false)
defineProps({compact:Boolean})
const ChatNavigationHelp=defineAsyncComponent(()=>import('./ChatNavigationHelp.vue'))
</script>
<style scoped>.chat-help-entry{flex:none;margin-left:0!important}.chat-help-entry.is-compact span{display:none}.chat-help-entry.is-compact{padding:8px}@media(max-width:900px){.chat-help-entry span{display:none}.chat-help-entry{padding:8px}}</style>
