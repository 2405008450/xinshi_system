<template><span v-if="showEntry" class="auto-draft-status" :class="{'has-error':autoDraftState.error||cloudDraftState.error}" :title="autoDraftState.error||cloudDraftState.error||'停止输入400毫秒后本机备份，约3秒合并同步云端；打开表单自动读取。'">{{autoDraftState.error||cloudDraftState.error?'草稿仅本机备份':cloudDraftState.saving?'草稿同步中…':cloudDraftState.pending?'草稿待同步':'自动保存已开启'}}</span></template>
<script setup>
import {onMounted} from 'vue'
import {autoDraftState,refreshAutoDrafts} from '@/utils/autoDrafts'
import {cloudDraftState} from '@/utils/cloudDrafts'
defineProps({showEntry:{type:Boolean,default:true}})
onMounted(refreshAutoDrafts)
</script>
<style scoped>.auto-draft-status{font-size:12px;color:#64748b;white-space:nowrap}.auto-draft-status.has-error{color:var(--el-color-danger)}</style>
