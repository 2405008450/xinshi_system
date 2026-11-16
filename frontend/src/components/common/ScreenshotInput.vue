<template>
  <div v-if="type==='textarea' || allowScreenshots" ref="root" class="app-screenshot-input" :data-screenshot-uploading="uploading" @beforeinput.capture="rememberSelection" @paste.capture="paste" @drop.capture="drop" @dragover.prevent>
    <component :is="autocomplete ? ElAutocomplete : BaseInput" ref="control" v-bind="$attrs" :type="type" :readonly="readonly || uploading" :maxlength="effectiveMax" :model-value="enabled?editorText:modelValue" @update:model-value="update" @input="inputChanged" @change="value=>$emit('change',outputValue(value))"><template v-for="(_,name) in $slots" #[name]="data"><slot :name="name" v-bind="data" /></template></component>
    <div v-if="enabled && !readonly && !hideScreenshotTools" class="app-screenshot-tools">
      <label>
        <span>{{ uploading ? '正在上传…' : allowInvoiceFiles ? '上传截图或发票文件' : '插入截图' }}</span>
        <input type="file" :accept="allowInvoiceFiles ? 'image/*,.pdf,application/pdf,.ofd,application/ofd' : 'image/*'" multiple :disabled="uploading" @change="choose" />
      </label>
      <small>{{ allowInvoiceFiles ? '支持拖入截图、PDF 或 OFD，发票文件最大 10 MB' : chat ? '聊天截图保留30天' : '支持粘贴截图，长期保存' }}</small>
      <small v-if="uploadHelp" class="app-screenshot-upload-help">{{ uploadHelp }}</small>
    </div>
    <small v-if="enabled && ids.length && !allowInvoiceFiles" class="app-screenshot-position">▧ 表示截图位置，以下为图文顺序预览。</small>
    <ScreenshotText v-if="enabled && ids.length" :text="String(modelValue||'')" :show-text="!allowInvoiceFiles" :removable="!readonly&&!uploading"
      :invoice-drag="allowInvoiceFiles" :invoice-order-no="invoiceOrderNo" @remove="remove" />
    <small v-if="allowInvoiceFiles && ids.length" class="invoice-drag-help">拖动附件到其他订单的发票上传区。{{desktopInvoiceDrag?'点击「准备拖出」后，可拖到桌面、微信或企微。':'可下载附件，再从下载文件夹拖到桌面、微信或企微。'}}</small>
    <span v-if="error" role="alert" class="app-screenshot-error">{{ error }}<button type="button" @click="error=''">×</button></span>
  </div>
  <BaseInput v-else ref="control" v-bind="$attrs" :type="type" :model-value="modelValue" @update:model-value="value=>$emit('update:modelValue',value)" @input="value=>$emit('input',value)" @change="value=>$emit('change',value)"><template v-for="(_,name) in $slots" #[name]="data"><slot :name="name" v-bind="data" /></template></BaseInput>
</template>
<script setup>
import { computed,defineAsyncComponent,nextTick,onBeforeUnmount,onMounted,ref,useAttrs } from 'vue'
import { ElAutocomplete, ElInput as BaseInput } from 'element-plus'
import 'element-plus/es/components/autocomplete/style/css'
import 'element-plus/es/components/input/style/css'
import { insertScreenshot, invoiceDragType, screenshotEditorText, screenshotIds, screenshotMarker, screenshotParts, updateScreenshotText } from '@/utils/screenshotReferences'
import { registerScreenshotUpload } from '@/utils/screenshotUploads'
defineOptions({inheritAttrs:false})
const ScreenshotText=defineAsyncComponent(()=>import('./ScreenshotText.vue'))
const props=defineProps({modelValue:[String,Number],type:{type:String,default:'text'},autocomplete:Boolean,allowScreenshots:Boolean,hideScreenshotTools:Boolean,allowInvoiceFiles:Boolean,invoiceRequestId:String,invoiceOrderNo:String,uploadHelp:String,screenshotLimit:{type:Number,default:9}})
const desktopInvoiceDrag=Boolean(window.xinshiDesktop?.prepareInvoiceFile && window.xinshiDesktop?.dragStatementFile)
const emit=defineEmits(['update:modelValue','input','change','uploading-change','attachment-added'])
const attrs=useAttrs(),control=ref(),root=ref(),enabled=ref(true),chat=ref(false),uploading=ref(false),error=ref('')
const ids=computed(()=>screenshotIds(props.modelValue)),editorText=computed(()=>screenshotEditorText(props.modelValue)),readonly=computed(()=>attrs.disabled!==undefined&&attrs.disabled!==false||attrs.readonly!==undefined&&attrs.readonly!==false)
const effectiveMax=computed(()=>enabled.value&&ids.value.length&&attrs.maxlength?Math.max(1,Number(attrs.maxlength)-(String(props.modelValue).length-editorText.value.length)):attrs.maxlength)
let disposed=false
let pendingFiles = []
let selection
onBeforeUnmount(()=>{disposed=true})
defineExpose(new Proxy({}, {get:(_,key)=>{if(key==='addScreenshots')return add;const value=control.value?.[key];return typeof value==='function'?value.bind(control.value):value},has:(_,key)=>key==='addScreenshots'||key in(control.value||{})}))
onMounted(()=>{if(root.value){enabled.value=!root.value.closest('[data-screenshot-editor="own"]');chat.value=!!root.value.closest('.group-composer,.discussion-chat__composer,.chat-composer,.project-chat-panel')}})
function rememberSelection(event) {
  const field = event.target
  let start = field.selectionStart, end = field.selectionEnd
  if (!Number.isInteger(start) || event.inputType === 'deleteByDrag') { selection = undefined; return }
  if (start === end && event.inputType === 'deleteContentBackward' && field.value[start - 1] === screenshotMarker) start--
  if (start === end && event.inputType === 'deleteContentForward' && field.value[end] === screenshotMarker) end++
  selection = { value: field.value, start, end }
  const captured = selection
  queueMicrotask(() => { if (selection === captured) selection = undefined })
}
function outputValue(value){return enabled.value ? updateScreenshotText(props.modelValue, value, selection) : value}
function update(value){emit('update:modelValue',outputValue(value))}
function inputChanged(value){emit('input',outputValue(value))}
function remove(id){
  const value = screenshotParts(props.modelValue).filter(part => part.id !== id).map(part => part.token || part.text).join('')
  emit('update:modelValue',value);emit('input',value);emit('change',value)
}
function invoiceFileExtension(file) {
  if (!props.allowInvoiceFiles) return null
  return file.name.match(/\.(pdf|ofd)$/i)?.[1].toLowerCase()
    || ({'application/pdf':'pdf', 'application/ofd':'ofd'})[file.type]
}
const reservedReference = 'screenshot://00000000-0000-0000-0000-000000000000#' + '0'.repeat(64)
async function add(files) {
  if (!files.length || !enabled.value || readonly.value) return
  pendingFiles.push(...files)
  if (uploading.value) return
  error.value = ''
  uploading.value = true
  const field = root.value?.querySelector('textarea, input:not([type=file])')
  let start = field?.selectionStart ?? editorText.value.length
  let end = field?.selectionEnd ?? start
  emit('uploading-change', true)
  let complete, savedValue
  registerScreenshotUpload(root.value, new Promise(resolve => { complete = resolve }))
  const limitMessage = props.allowInvoiceFiles ? '每个编辑框最多9个附件' : '每个编辑框最多9张截图'
  try {
    const {uploadEditorScreenshot, uploadInvoiceFile} = await import('@/utils/uploadEditorScreenshot')
    for (const file of pendingFiles) {
      if (disposed) return
      if (ids.value.length >= props.screenshotLimit) throw new Error(limitMessage)
      if (attrs.maxlength && insertScreenshot(props.modelValue, reservedReference, start, end).length > Number(attrs.maxlength)) {
        throw new Error('当前字段剩余空间不足，请减少文字或附件')
      }
      const extension = invoiceFileExtension(file)
      const currentValue = props.modelValue
      const attachment = extension
        ? await uploadInvoiceFile(file, extension, props.invoiceRequestId)
        : await uploadEditorScreenshot(file, chat.value ? 'chat' : 'business')
      if (disposed || props.modelValue !== currentValue) return
      if (ids.value.length >= props.screenshotLimit) throw new Error(limitMessage)
      savedValue = insertScreenshot(props.modelValue, attachment.reference, start, end)
      start++
      end = start
      emit('update:modelValue', savedValue)
      emit('attachment-added')
      await nextTick()
    }
  } catch (e) {
    error.value = e.detail || e.message || '附件上传失败'
  } finally {
    pendingFiles = []
    if (savedValue && !disposed) {
      emit('input', savedValue)
      emit('change', savedValue)
    }
    uploading.value = false
    if (savedValue && !disposed) nextTick(() => { field?.focus(); field?.setSelectionRange(start, start) })
    emit('uploading-change', false)
    complete(!error.value)
  }
}
function paste(event){if(!enabled.value||readonly.value)return;const files=Array.from(event.clipboardData?.files||[]).filter(file=>file.type.startsWith('image/'));if(files.length){event.preventDefault();event.stopPropagation();void add(files)}}
async function drop(event) {
  if (!enabled.value) return
  const dropped = Array.from(event.dataTransfer?.files || [])
  const internalInvoice = event.dataTransfer?.getData(invoiceDragType)
  if (!dropped.length && !internalInvoice) return
  const files = dropped.filter(file => file.type.startsWith('image/') || invoiceFileExtension(file))
  if (!files.length && !props.allowInvoiceFiles) return
  event.preventDefault()
  event.stopPropagation()
  if (readonly.value || uploading.value) return
  if (files.length) void add(files)
  else if (internalInvoice) {
    try {
      const {url,name} = JSON.parse(internalInvoice)
      const source = new URL(url)
      if (source.protocol !== 'blob:' || source.origin !== window.location.origin) throw new Error()
      const response = await fetch(source)
      if (!response.ok) throw new Error()
      const blob = await response.blob()
      const file = new File([blob], name, {type:blob.type})
      if (!file.type.startsWith('image/') && !invoiceFileExtension(file)) throw new Error()
      if (!disposed) await add([file])
    } catch {
      error.value = '无法读取拖出的发票，请下载附件后再拖入。'
    }
  }
  else error.value = '请拖入 PDF、OFD 或图片文件'
}
function choose(event){void add(Array.from(event.target.files||[]));event.target.value=''}
</script>
<style scoped>.app-screenshot-input{width:100%;min-width:0}.app-screenshot-tools{display:flex;align-items:center;flex-wrap:wrap;gap:2px 10px;font-size:11px;margin-top:4px;color:#94a3b8;line-height:1.5}.app-screenshot-tools small{font-size:inherit}.app-screenshot-upload-help{color:var(--el-text-color-secondary)}.app-screenshot-tools label{cursor:pointer;color:var(--el-color-primary)}.app-screenshot-tools input{display:none}.app-screenshot-error{display:block;color:#dc2626;font-size:12px}.app-screenshot-error button{border:0;background:none;cursor:pointer}</style>

<style scoped>.app-screenshot-input :deep(.screenshot-previews){max-height:160px;overflow-y:auto}.app-screenshot-input :deep(.screenshot-preview .el-image){height:90px;max-width:180px}</style>
<style scoped>.invoice-drag-help{display:block;margin-top:6px;color:var(--el-text-color-secondary);line-height:1.5}</style>
<style scoped>
.app-screenshot-position { display:block; color:var(--el-text-color-secondary); margin-top:6px }
.app-screenshot-input > :deep(.screenshot-text) { display:flex; max-height:220px; overflow:auto; padding:6px; border:1px solid var(--el-border-color-lighter); border-radius:4px }
</style>
