<template>
  <div class="auto-draft-center" :class="{'is-hidden-entry':!showEntry}">
    <el-badge v-if="showEntry" :value="autoDraftState.records.length" :hidden="!autoDraftState.records.length"><el-button text :type="autoDraftState.error?'danger':undefined" @click="open">草稿</el-button></el-badge>
    <DraggableFormDialog v-model="visible" title="本机可恢复草稿" append-to-body width="min(860px, calc(100vw - 32px))" top="5vh">
      <p>停止输入{{autoDraftState.delay===400?'400毫秒':`${autoDraftState.delay/1000}秒`}}后保留本机草稿，不提交业务数据。按账号、页面及记录隔离，保留7天、最多100份；超出数量或容量预算时清理最早的通用草稿。密码和文件本体不保留。已有专用草稿的表单仍在打开时提示恢复。</p>
      <el-alert v-if="autoDraftState.error" :title="autoDraftState.error" type="warning" :closable="false" />
      <el-empty v-if="!displayRecords.length" description="暂无本机未提交草稿" :image-size="60" />
      <el-table v-else :data="displayRecords" border><el-table-column prop="title" label="表单 / 编辑框" min-width="180" /><el-table-column prop="record" label="记录" min-width="110" show-overflow-tooltip /><el-table-column label="保存时间" min-width="170"><template #default="{row}">{{formatBusinessDateTime(row.savedAt)}}</template></el-table-column><el-table-column label="操作" width="150"><template #default="{row}"><el-button link type="primary" @click="restore(row)">恢复</el-button><el-button link @click="discard(row)">放弃</el-button></template></el-table-column></el-table>
      <template #footer><el-button @click="visible=false">关闭</el-button></template>
    </DraggableFormDialog>
  </div>
</template>
<script setup>
import {ref,computed,watch,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from './DraggableFormDialog.vue'
import {autoDraftState,refreshAutoDrafts,restoreAutoDraft,discardAutoDraft} from '@/utils/autoDrafts'
import {formatBusinessDateTime} from '@/utils/dateTime'
const props=defineProps({showEntry:{type:Boolean,default:true}})
const visible=ref(false),recoveryId=ref('')
const displayRecords=computed(()=>recoveryId.value?autoDraftState.records.filter(row=>row.id===recoveryId.value):autoDraftState.records)
watch(()=>autoDraftState.error,value=>{if(value&&!props.showEntry)ElMessage.warning(value)})
function offer(event){refreshAutoDrafts();recoveryId.value=event.detail?.id||'';if(displayRecords.value.length)visible.value=true}
onMounted(()=>{refreshAutoDrafts();window.addEventListener('auto-draft-available',offer)})
onBeforeUnmount(()=>window.removeEventListener('auto-draft-available',offer))
function open(){recoveryId.value='';refreshAutoDrafts();visible.value=true}
function discard(row){discardAutoDraft(row.id);if(recoveryId.value)visible.value=false}
function restore(row){if(restoreAutoDraft(row.id)){visible.value=false;ElMessage.success('草稿已恢复，请核对后按原流程保存或提交')}else ElMessage.info('请先打开草稿对应的页面及同一条记录的编辑表单，再点击恢复')}
</script>
<style scoped>.auto-draft-center{display:inline-flex;align-items:center}.auto-draft-center.is-hidden-entry{display:contents}.auto-draft-center p{font-size:13px;color:#64748b;line-height:1.7}</style>
