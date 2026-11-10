<template>
  <div class="my-thoughts" data-auto-draft="off">
    <p>记录想法、问题和后续探索方向，内容仅本人可见，自动保存。</p>
    <el-input v-model="form.content" type="textarea" :rows="8" maxlength="30000" show-word-limit placeholder="在这里写下我的思考与发散……" aria-label="我的思考与发散内容" />
    <small role="status">{{status.error|| (status.state==='synced'?'已同步云端':status.state==='saving'?'正在同步云端……':'编辑后自动保存，停止输入400毫秒保留本机备份，约3秒合并同步云端')}}</small>
    <ThoughtAssistant :content="form.content" @append="form.content = [form.content, $event].filter(Boolean).join('\n\n')" />
  </div>
</template>
<script setup>
import {onMounted,reactive} from 'vue'
import {useFormDraft} from '@/composables/useFormDraft'
import {cloudDraftStatus} from '@/utils/cloudDrafts'
import ThoughtAssistant from './ThoughtAssistant.vue'
const form=reactive({content:''})
const {beginDraft}=useFormDraft({namespace:'workbench-thoughts',form,createDefault:()=>({content:''})})
const status=cloudDraftStatus('form:workbench-thoughts','mine')
onMounted(()=>beginDraft('mine'))
</script>
<style scoped>.my-thoughts p,.my-thoughts small{color:#64748b}.my-thoughts small{display:block;margin-top:8px}</style>
