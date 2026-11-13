<template>
  <div v-if="type==='textarea'" ref="root" class="app-screenshot-input" :data-screenshot-uploading="uploading" @paste.capture="paste" @drop.capture="drop" @dragover.prevent>
    <BaseInput ref="control" v-bind="$attrs" :type="type" :maxlength="effectiveMax" :model-value="enabled?plain:modelValue" @update:model-value="update" @input="value=>$emit('input',outputValue(value))" @change="value=>$emit('change',outputValue(value))"><template v-for="(_,name) in $slots" #[name]="data"><slot :name="name" v-bind="data" /></template></BaseInput>
    <div v-if="enabled && !readonly && showScreenshotTools" class="app-screenshot-tools">
      <label>
        <span>{{ uploading ? '正在上传…' : allowInvoiceFiles ? '上传截图或发票文件' : '插入截图' }}</span>
        <input type="file" :accept="allowInvoiceFiles ? 'image/*,.pdf,application/pdf,.ofd,application/ofd' : 'image/*'" multiple :disabled="uploading" @change="choose" />
      </label>
      <small>{{ allowInvoiceFiles ? '支持拖入截图、PDF 或 OFD，发票文件最大 10 MB' : chat ? '聊天截图保留30天' : '支持粘贴截图，长期保存' }}</small>
    </div>
    <ScreenshotText v-if="enabled && ids.length" :text="String(modelValue||'')" :show-text="false" :removable="!readonly&&!uploading" @remove="remove" />
    <span v-if="error" role="alert" class="app-screenshot-error">{{ error }}<button type="button" @click="error=''">×</button></span>
  </div>
  <BaseInput v-else ref="control" v-bind="$attrs" :type="type" :model-value="modelValue" @update:model-value="value=>$emit('update:modelValue',value)" @input="value=>$emit('input',value)" @change="value=>$emit('change',value)"><template v-for="(_,name) in $slots" #[name]="data"><slot :name="name" v-bind="data" /></template></BaseInput>
</template>
<script setup>
import { computed,defineAsyncComponent,nextTick,onBeforeUnmount,onMounted,ref,useAttrs } from 'vue'
import { ElInput as BaseInput } from 'element-plus'
import 'element-plus/es/components/input/style/css'
import { screenshotIds,screenshotText,screenshotValue } from '@/utils/screenshotReferences'
import { registerScreenshotUpload } from '@/utils/screenshotUploads'
defineOptions({inheritAttrs:false})
const ScreenshotText=defineAsyncComponent(()=>import('./ScreenshotText.vue'))
const props=defineProps({modelValue:[String,Number],type:{type:String,default:'text'},showScreenshotTools:{type:Boolean,default:true},allowInvoiceFiles:Boolean,invoiceRequestId:String})
const emit=defineEmits(['update:modelValue','input','change','uploading-change','attachment-added'])
const attrs=useAttrs(),control=ref(),root=ref(),enabled=ref(true),chat=ref(false),uploading=ref(false),error=ref('')
const ids=computed(()=>screenshotIds(props.modelValue)),plain=computed(()=>screenshotText(props.modelValue)),readonly=computed(()=>attrs.disabled!==undefined&&attrs.disabled!==false||attrs.readonly!==undefined&&attrs.readonly!==false)
const effectiveMax=computed(()=>enabled.value&&ids.value.length&&attrs.maxlength?Math.max(0,Number(attrs.maxlength)-(screenshotValue('x',ids.value).length-1)):attrs.maxlength)
let disposed=false
onBeforeUnmount(()=>{disposed=true})
defineExpose(new Proxy({}, {get:(_,key)=>{const value=control.value?.[key];return typeof value==='function'?value.bind(control.value):value},has:(_,key)=>key in(control.value||{})}))
onMounted(()=>{if(root.value){enabled.value=!root.value.closest('.annotation-task-images,[data-screenshot-editor="own"]');chat.value=!!root.value.closest('.group-composer,.discussion-chat__composer,.chat-composer,.project-chat-panel')}})
function outputValue(value){return enabled.value?screenshotValue(value,ids.value):value}
function update(value){emit('update:modelValue',outputValue(value))}
function remove(id){const value=screenshotValue(plain.value,ids.value.filter(uid=>uid!==id));emit('update:modelValue',value);emit('input',value);emit('change',value)}
function invoiceFileExtension(file) {
  if (!props.allowInvoiceFiles) return null
  return file.name.match(/\.(pdf|ofd)$/i)?.[1].toLowerCase()
    || ({'application/pdf':'pdf', 'application/ofd':'ofd'})[file.type]
}
const reservedReference = 'screenshot://00000000-0000-0000-0000-000000000000#' + '0'.repeat(64)
async function add(files) {
  if (!files.length || !enabled.value || readonly.value || uploading.value) return
  error.value = ''
  uploading.value = true
  emit('uploading-change', true)
  let complete, savedValue
  registerScreenshotUpload(root.value, new Promise(resolve => { complete = resolve }))
  const limitMessage = props.allowInvoiceFiles ? '每个编辑框最多9个附件' : '每个编辑框最多9张截图'
  try {
    const {uploadEditorScreenshot, uploadInvoiceFile} = await import('@/utils/uploadEditorScreenshot')
    for (const file of files) {
      if (disposed) return
      if (ids.value.length >= 9) throw new Error(limitMessage)
      if (attrs.maxlength && screenshotValue(plain.value, [...ids.value, reservedReference]).length > Number(attrs.maxlength)) {
        throw new Error('当前字段剩余空间不足，请减少文字或附件')
      }
      const extension = invoiceFileExtension(file)
      const attachment = extension
        ? await uploadInvoiceFile(file, extension, props.invoiceRequestId)
        : await uploadEditorScreenshot(file, chat.value ? 'chat' : 'business')
      if (disposed) return
      if (ids.value.length >= 9) throw new Error(limitMessage)
      savedValue = screenshotValue(plain.value, [...ids.value, attachment.id])
      emit('update:modelValue', savedValue)
      emit('attachment-added')
      await nextTick()
    }
  } catch (e) {
    error.value = e.detail || e.message || '附件上传失败'
  } finally {
    if (savedValue && !disposed) {
      emit('input', savedValue)
      emit('change', savedValue)
    }
    uploading.value = false
    emit('uploading-change', false)
    complete(!error.value)
  }
}
function paste(event){if(!enabled.value||readonly.value)return;const files=Array.from(event.clipboardData?.files||[]).filter(file=>file.type.startsWith('image/'));if(files.length){if(!event.clipboardData.getData('text/plain'))event.preventDefault();event.stopPropagation();void nextTick().then(()=>add(files))}}
function drop(event) {
  if (!enabled.value || chat.value) return
  const dropped = Array.from(event.dataTransfer?.files || [])
  if (!dropped.length) return
  const files = dropped.filter(file => file.type.startsWith('image/') || invoiceFileExtension(file))
  if (!files.length && !props.allowInvoiceFiles) return
  event.preventDefault()
  event.stopPropagation()
  if (readonly.value || uploading.value) return
  if (files.length) void add(files)
  else error.value = '请拖入 PDF、OFD 或图片文件'
}
function choose(event){void add(Array.from(event.target.files||[]));event.target.value=''}
</script>
<style scoped>.app-screenshot-input{width:100%;min-width:0}.app-screenshot-tools{display:flex;align-items:center;gap:10px;font-size:11px;margin-top:4px;color:#94a3b8;line-height:1.5}.app-screenshot-tools label{cursor:pointer;color:var(--el-color-primary)}.app-screenshot-tools input{display:none}.app-screenshot-error{display:block;color:#dc2626;font-size:12px}.app-screenshot-error button{border:0;background:none;cursor:pointer}</style>

<style scoped>.app-screenshot-input :deep(.screenshot-previews){max-height:160px;overflow-y:auto}.app-screenshot-input :deep(.screenshot-preview .el-image){height:90px;max-width:180px}</style>
