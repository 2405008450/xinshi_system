<template><DraggableFormDialog class="chat-navigation-help-dialog" v-model="visible" title="会话使用帮助" width="min(1080px,calc(100vw - 32px))" top="5vh" append-to-body><ProjectOperationHelp title="会话使用帮助" intro="查看群目录、分页、收藏、最近关闭及项目协作规则。" :sections="chatNavigationHelpSections" :updated-at="chatNavigationHelpUpdatedAt" module-label="会话" id-prefix="chat-help-" /><template #footer><el-button @click="visible=false">关闭</el-button></template></DraggableFormDialog></template>
<script setup>
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import ProjectOperationHelp from '@/components/common/ProjectOperationHelp.vue'
import {chatNavigationHelpSections,chatNavigationHelpUpdatedAt} from '@/utils/chatNavigationHelp'
const visible=defineModel({type:Boolean,default:false})
</script>

<style>.chat-navigation-help-dialog{display:flex;flex-direction:column;height:min(820px,90vh);max-height:90vh;overflow:hidden}.chat-navigation-help-dialog>.el-dialog__body{display:flex;flex:1;min-height:0;overflow:hidden}.chat-navigation-help-dialog>.el-dialog__body>.project-operation-help{flex:1;min-width:0}.chat-navigation-help-dialog>.el-dialog__header,.chat-navigation-help-dialog>.el-dialog__footer{flex:none}</style>
