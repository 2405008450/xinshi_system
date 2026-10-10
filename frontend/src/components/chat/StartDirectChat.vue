<template>
  <el-popover v-model:visible="visible" trigger="click" placement="bottom-start" :width="320" popper-class="chat-session-popover" @show="search">
    <template #reference><el-button size="small" :disabled="!phaseOneEnabled" :title="phaseOneEnabled ? '发起内部私聊' : '等待聊天数据库迁移'" @mousedown.stop>发起私聊</el-button></template>
    <div class="direct-user-search"><el-input v-model="keyword" clearable placeholder="搜索姓名、账号" @keyup.enter="search" /><el-button @click="search">查询</el-button></div>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-loading="loading" class="direct-user-list">
      <el-button v-for="user in users" :key="user.id" link :disabled="opening" @click="open(user)">{{ user.name }} <small>{{ user.username }}</small></el-button>
      <el-empty v-if="!loading && !users.length" description="没有匹配的用户" :image-size="40" />
    </div>
  </el-popover>
</template>
<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { chatRequest } from '@/api/projectChat'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
const { refresh, phaseOneEnabled } = useAnnotationFollowed()
const visible = ref(false), keyword = ref(''), users = ref([]), loading = ref(false), opening = ref(false), error = ref('')
let timer, controller, sequence = 0
async function search() {
  clearTimeout(timer); controller?.abort(); controller = new AbortController()
  const requestId = ++sequence
  loading.value = true; error.value = ''
  try {
    const data = await chatRequest('users', { params: { keyword: keyword.value }, signal: controller.signal })
    if (requestId === sequence) users.value = data.items
  } catch (e) { if (requestId === sequence && !controller.signal.aborted) error.value = e.detail || e.message || '用户加载失败' }
  finally { if (requestId === sequence) loading.value = false }
}
watch(keyword, value => { clearTimeout(timer); if (!value) search(); else timer = setTimeout(search, 400) })
async function open(user) {
  opening.value = true
  try {
    const data = await chatRequest('direct/conversations', { method: 'post', data: { userId: user.id } })
    useProjectChatDock().openChat({ projectId: data.id, projectType: 'direct', title: data.title, subtitle: data.subtitle })
    visible.value = false; await refresh()
  } catch (e) { ElMessage.error(e.detail || e.message || '发起私聊失败') }
  finally { opening.value = false }
}
onBeforeUnmount(() => { ++sequence; clearTimeout(timer); controller?.abort() })
</script>
<style scoped>
.direct-user-search{display:flex;gap:6px}.direct-user-list{display:flex;flex-direction:column;align-items:stretch;max-height:320px;overflow:auto;min-height:60px;margin-top:10px}.direct-user-list .el-button{margin:0;justify-content:flex-start;padding:9px}.direct-user-list small{color:#94a3b8;margin-left:8px}
</style>
