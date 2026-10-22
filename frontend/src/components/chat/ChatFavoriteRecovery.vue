<template>
  <DraggableFormDialog v-model="visible" title="恢复取消关注的项目" width="min(660px, calc(100vw - 32px))" top="5vh" class="chat-favorite-recovery" append-to-body :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @closed="reset">
    <p class="favorite-recovery-hint">恢复后重新出现在收藏夹，保留聊天记录、参与人和未读状态。每次最多恢复 10 个。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link :disabled="saving" @click="load">重试</el-button></el-alert>
    <div v-loading="loading">
      <el-checkbox-group v-model="selected" :max="10" :disabled="saving">
        <div v-for="item in items" :key="item.projectId" class="favorite-recovery-row"><el-checkbox :value="item.projectId"><span>{{ item.projectName || '未命名项目' }}</span><small>{{ item.orderNo }}</small></el-checkbox></div>
      </el-checkbox-group>
      <el-empty v-if="!loading && !error && !items.length" description="没有可恢复的项目" :image-size="44" />
    </div>
    <p v-for="failure in failures" :key="failure.projectId" class="favorite-recovery-failure" role="alert">{{ names.get(failure.projectId) || failure.projectId }}：{{ failure.reason }}</p>
    <el-pagination v-if="total > 10" small layout="prev, pager, next, total" :page-size="10" :total="total" v-model:current-page="page" :disabled="saving || loading" @current-change="load" />
    <template #footer><span class="favorite-recovery-selected">已选 {{ selected.length }}/10</span><el-button :disabled="saving" @click="visible=false">关闭</el-button><el-button :disabled="saving || loading || !total" @click="restoreAll">{{ total > 10 ? '恢复前10个' : '全部恢复' }}</el-button><el-button type="primary" :loading="saving" :disabled="loading || !selected.length" @click="restore(selected)">恢复所选</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { annotationChatRequest } from '@/api/projectChat'
const visible = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['restored'])
const items=ref([]),selected=ref([]),total=ref(0),page=ref(1),loading=ref(false),saving=ref(false),error=ref(''),failures=ref([])
const names=new Map()
let controller, sequence=0
function reset(){controller?.abort();++sequence;selected.value=[];failures.value=[];error.value='';items.value=[];names.clear()}
async function load(){
  controller?.abort();controller=new AbortController();const current=++sequence;loading.value=true;error.value=''
  try{
    const data=await annotationChatRequest('', 'unfollowed-projects',{params:{offset:(page.value-1)*10,limit:10},signal:controller.signal})
    if(current!==sequence)return
    total.value=data.total;items.value=data.items
    for(const item of items.value)names.set(item.projectId,item.orderNo)
    const last=Math.max(1,Math.ceil(total.value/10))
    if(page.value>last){page.value=last;void load()}
  }catch(e){if(current===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'恢复列表加载失败'}
  finally{if(current===sequence)loading.value=false}
}
async function restore(ids){
  if(saving.value||!ids.length||ids.length>10)return
  saving.value=true;failures.value=[];error.value=''
  try{
    const data=await annotationChatRequest('', 'restore-favorites',{method:'post',data:{projectIds:[...ids]}})
    const done=new Set(data.restored);selected.value=selected.value.filter(id=>!done.has(id));failures.value=data.failed||[]
    if(done.size){emit('restored');ElMessage.success(`已恢复 ${done.size} 个关注项目`)}
    await load()
  }catch(e){error.value=e.detail||e.message||'恢复失败，请重试'}
  finally{saving.value=false}
}
async function restoreAll(){
  if(saving.value)return
  if(page.value!==1){page.value=1;await load()}
  if(!error.value)await restore(items.value.slice(0,10).map(item=>item.projectId))
}
watch(visible,value=>{if(value){reset();page.value=1;void load()}})
onBeforeUnmount(reset)
</script>
<style>
.chat-favorite-recovery{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.chat-favorite-recovery>.el-dialog__header,.chat-favorite-recovery>.el-dialog__footer{flex:none}.chat-favorite-recovery>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.chat-favorite-recovery>.el-dialog__footer{background:#f8fafc;border-top:1px solid #e2e8f0}
</style>
<style scoped>
.favorite-recovery-hint,.favorite-recovery-selected{font-size:12px;color:#64748b}.favorite-recovery-row{display:block;padding:9px 0;border-bottom:1px solid #e2e8f0}.favorite-recovery-row :deep(.el-checkbox){height:auto;max-width:100%}.favorite-recovery-row :deep(.el-checkbox__label){white-space:normal;overflow-wrap:anywhere}.favorite-recovery-row small{display:block;color:#64748b;margin-top:4px}.favorite-recovery-failure{font-size:12px;color:#b91c1c}.favorite-recovery-selected{margin-right:auto}
</style>
