<template>
  <DraggableFormDialog :model-value="true" title="分工进度与修改记录" width="min(800px, calc(100vw - 32px))" top="5vh" append-to-body :before-close="close" @update:model-value="value => { if (!value) $emit('close') }">
    <div v-loading="loading"><el-alert v-if="error" :title="error" type="error" :closable="false" /><template v-if="task"><p>{{ task.task_no }} · {{ task.name }}</p><el-progress :percentage="task.progress" /><AppForm ref="form" :model="draft" :rules="rules" label-position="top"><el-form-item label="进度（1—100）" prop="percentage"><el-input-number v-model="draft.percentage" :min="1" :max="100" :precision="0" /></el-form-item><el-form-item label="具体进度"><el-input v-model="draft.content" type="textarea" :rows="3" maxlength="30000" /></el-form-item><el-form-item label="修改原因" prop="reason"><el-input v-model="draft.reason" type="textarea" :rows="2" maxlength="3000" placeholder="回退进度必须填写原因" /></el-form-item></AppForm><article v-for="entry in task.progress_history" :key="entry.id" class="allocation-progress-record"><strong>{{ entry.previous_percentage }}% → {{ entry.percentage }}%</strong><small>{{ entry.author_name }} · {{ formatTime(entry.created_at) }}</small><p>{{ entry.content || '-' }}</p><p v-if="entry.reason">{{ entry.reason }}</p></article></template></div>
    <template #footer><el-button :disabled="saving" @click="$emit('close')">关闭</el-button><el-button type="primary" :loading="saving" :disabled="!task || loading" @click="save">保存进度</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,onMounted,reactive,ref} from 'vue'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {getDevelopmentTask,saveDevelopmentProgress} from '@/api/technicalDevelopment'
import {formatBusinessDateTimeMinute as formatTime} from '@/utils/datetime'
const props=defineProps({taskId:{type:String,required:true}}),emit=defineEmits(['close','changed'])
const task=ref(null),form=ref(null),loading=ref(false),saving=ref(false),error=ref(''),draft=reactive({percentage:1,content:'',reason:''})
const rules=computed(()=>({percentage:[{required:true,type:'number',min:1,max:100,message:'请输入1—100的整数',trigger:'change'}],reason:[{validator:(_,value,done)=>done(draft.percentage<(task.value?.progress||0)&&!value.trim()?new Error('进度回退必须填写原因'):undefined),trigger:'blur'}]}))
function close(done){if(!saving.value){emit('close');done()}}
async function load(){loading.value=true;try{task.value=await getDevelopmentTask(props.taskId);draft.percentage=task.value.progress||1}catch(e){error.value=e.detail||'加载失败'}finally{loading.value=false}}
async function save(){if(saving.value||!await form.value.validate().catch(()=>false))return;saving.value=true;error.value='';try{task.value=await saveDevelopmentProgress(props.taskId,{...draft,revision:task.value.revision});draft.content='';draft.reason='';emit('changed')}catch(e){error.value=typeof e.detail==='string'?e.detail:'保存失败'}finally{saving.value=false}}
onMounted(load)
</script>
<style scoped>.allocation-progress-record{white-space:pre-wrap;overflow-wrap:anywhere;border-top:1px solid var(--el-border-color);padding:12px 0}.allocation-progress-record small{display:block;color:var(--el-text-color-secondary)}</style>
