<template>
  <div class="custom-field-image">
    <el-image
      v-if="previewUrl"
      class="custom-field-image__preview"
      :src="previewUrl"
      :preview-src-list="[previewUrl]"
      fit="cover"
      preview-teleported
    />
    <div v-else-if="loading" class="custom-field-image__placeholder">图片加载中…</div>
    <div v-else-if="modelValue" class="custom-field-image__placeholder custom-field-image__placeholder--error">图片加载失败</div>
    <el-upload
      v-if="!readonly"
      :show-file-list="false"
      :http-request="upload"
      accept="image/jpeg,image/png,image/gif,image/webp"
      :disabled="disabled || uploading"
    >
      <el-button :loading="uploading" :disabled="disabled">{{ modelValue ? '替换图片' : '上传图片' }}</el-button>
    </el-upload>
    <el-button v-if="!readonly && modelValue" type="danger" link :disabled="disabled || uploading" @click="remove">删除图片</el-button>
    <span v-if="!readonly" class="custom-field-image__tip">JPEG/PNG/GIF/WebP，最大 10MB</span>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { deletePendingCustomFieldImage, getCustomFieldImageBlob, uploadCustomFieldImage } from '@/api/annotationOps'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'

const props=defineProps({
  modelValue:{type:String,default:null},
  projectId:{type:String,required:true},
  fieldId:{type:String,required:true},
  disabled:{type:Boolean,default:false},
  readonly:{type:Boolean,default:false},
})
const emit=defineEmits(['update:modelValue'])
const previewUrl=ref(''),loading=ref(false),uploading=ref(false)
const pendingIds=new Set()
let loadSequence=0,disposed=false

const revokePreview=()=>{if(previewUrl.value){URL.revokeObjectURL(previewUrl.value);previewUrl.value=''}}
const loadPreview=async id=>{
  const current=++loadSequence
  revokePreview()
  if(!id)return
  loading.value=true
  try{
    const blob=await getCustomFieldImageBlob(id)
    if(current!==loadSequence)return
    previewUrl.value=URL.createObjectURL(blob)
  }catch(error){if(current===loadSequence)console.error('加载动态字段图片失败',error)}
  finally{if(current===loadSequence)loading.value=false}
}
const deleteIfPending=async id=>{
  if(!id||!pendingIds.has(id))return
  pendingIds.delete(id)
  try{await deletePendingCustomFieldImage(id)}catch(error){console.warn('清理待保存图片失败',error)}
}
const cleanupPending=async()=>{
  await Promise.allSettled([...pendingIds].map(deleteIfPending))
}
const markSaved=()=>pendingIds.clear()
const upload=async({file})=>{
  if(file.size>10*1024*1024)return ElMessage.warning('单张图片不能超过 10MB')
  uploading.value=true
  try{
    const previous=props.modelValue
    const image=await uploadCustomFieldImage(props.projectId,props.fieldId,file)
    pendingIds.add(image.id)
    if(disposed){await deleteIfPending(image.id);return}
    emit('update:modelValue',image.id)
    await deleteIfPending(previous)
  }catch(error){ElMessage.error(getLocalizedErrorMessage(error,'图片上传失败'))}
  finally{uploading.value=false}
}
const remove=async()=>{
  const previous=props.modelValue
  emit('update:modelValue',null)
  await deleteIfPending(previous)
}

watch(()=>props.modelValue,value=>loadPreview(value),{immediate:true})
onBeforeUnmount(()=>{disposed=true;loadSequence++;revokePreview();cleanupPending()})
defineExpose({cleanupPending,markSaved})
</script>

<style scoped>
.custom-field-image{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.custom-field-image__preview{width:88px;height:64px;border:1px solid var(--el-border-color);border-radius:6px}.custom-field-image__placeholder{width:88px;height:64px;display:flex;align-items:center;justify-content:center;border:1px dashed var(--el-border-color);border-radius:6px;color:var(--el-text-color-secondary);font-size:12px}.custom-field-image__placeholder--error{color:var(--el-color-danger)}.custom-field-image__tip{font-size:12px;color:var(--el-text-color-secondary)}
</style>
