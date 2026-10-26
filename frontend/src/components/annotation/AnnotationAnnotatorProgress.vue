<template>
  <section v-loading="loading">
    <slot v-if="!editable" name="track" />
    <div v-if="editable" class="progress-entry-panel annotator-entry">
      <div class="progress-entry-panel__header"><b>录入标注员情况</b></div>
      <AppForm ref="formRef" :model="form" :rules="rules" label-width="76px" size="small" class="progress-entry-form" :disabled="saving">
        <el-row :gutter="14" class="progress-entry-metadata">
          <el-col :xs="24" :sm="12"><el-form-item label="当前状态"><ReadonlyField :model-value="projectStatusLabel" source="auto" /></el-form-item></el-col>
          <el-col :xs="24" :sm="12"><el-form-item label="节点时间" prop="effectiveOn"><el-date-picker v-model="form.effectiveOn" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="标注员情况" prop="changeNote" label-width="124px" class="annotation-progress-note-item"><template #label><slot name="track">标注员情况</slot></template><el-input v-model="form.changeNote" type="textarea" aria-label="标注员具体情况" :rows="3" maxlength="10000" show-word-limit placeholder="填写标注员的安排、反馈或执行情况，支持粘贴截图" /></el-form-item>
      </AppForm>
      <div class="progress-entry-actions" />
    </div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false"><el-button link @click="reload">重新加载</el-button></el-alert>
    <slot name="history-notice" />
    <div class="progress-history-header"><b>标注员情况记录</b></div>
    <el-timeline><el-timeline-item v-for="row in rows" :key="row.id" :timestamp="formatBusinessDateTime(row.effectiveOn)" placement="top"><ScreenshotText :text="row.changeNote" /><p class="annotator-meta">{{ row.changedByName || '-' }} · 登记于 {{ formatBusinessDateTime(row.changedAt) }}</p></el-timeline-item></el-timeline>
    <el-empty v-if="!loading && !error && !rows.length" description="暂无标注员情况记录" :image-size="48" />
    <AnnotationProgressDeliveryDialog ref="deliveryRef" />
  </section>
</template>
<script setup>
import { computed,onBeforeUnmount,reactive,ref,watch } from 'vue'
import './annotationProgressHistory.css'
import { ElMessage } from 'element-plus'
import { getAnnotatorProgress,createAnnotatorProgress } from '@/api/annotationOps'
import { businessDateTimeInputValue,formatBusinessDateTime } from '@/utils/dateTime'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import AnnotationProgressDeliveryDialog from '@/components/chat/AnnotationProgressDeliveryDialog.vue'
const props=defineProps({projectId:String,projectTitle:String,projectStatusLabel:String,active:Boolean,editable:Boolean})
const emit=defineEmits(['saved'])
const formRef=ref(),deliveryRef=ref(),rows=ref([]),loading=ref(false),saving=ref(false),error=ref('')
const form=reactive({effectiveOn:businessDateTimeInputValue(),changeNote:''})
const rules={effectiveOn:[{required:true,message:'请选择节点时间'}],changeNote:[{required:true,whitespace:true,message:'请填写标注员情况'}]}
let controller,requestId=0
async function reload(){
  if(!props.projectId)return
  controller?.abort();controller=new AbortController();const current=++requestId;loading.value=true;error.value=''
  try{const result=await getAnnotatorProgress(props.projectId,{signal:controller.signal});if(current===requestId)rows.value=result}
  catch(e){if(current===requestId && e.code!=='ERR_CANCELED')error.value=e.detail || '标注员情况加载失败'}
  finally{if(current===requestId)loading.value=false}
}
async function save(){
  if(!props.editable || saving.value || loading.value || error.value || !await formRef.value?.validate().catch(()=>false))return
  const id=props.projectId;saving.value=true
  try{
    const chatDelivery=await deliveryRef.value.request(props.projectTitle,id);if(!chatDelivery)return
    await createAnnotatorProgress(id,{changeNote:form.changeNote.trim(),effectiveOn:form.effectiveOn.replace(' ','T')+'+08:00',chatDelivery})
    form.changeNote='';form.effectiveOn=businessDateTimeInputValue();ElMessage.success('标注员情况已保存');emit('saved');await reload()
  }catch(e){ElMessage.error(e.detail || '标注员情况保存失败')}
  finally{saving.value=false}
}
watch(()=>props.projectId,()=>{controller?.abort();++requestId;rows.value=[];error.value='';form.changeNote='';form.effectiveOn=businessDateTimeInputValue()})
watch(()=>[props.active,props.projectId],()=>{if(props.active)void reload()},{immediate:true})
onBeforeUnmount(()=>{controller?.abort();++requestId})
defineExpose({save,reload,hasDraft:()=>!!form.changeNote.trim(),busy:computed(()=>saving.value),unavailable:computed(()=>loading.value || !!error.value)})
</script>
<style scoped>.annotator-meta{font-size:12px;color:#64748b}</style>
