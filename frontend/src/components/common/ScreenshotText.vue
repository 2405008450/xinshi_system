<template>
  <span class="screenshot-text">
    <span v-if="showText" class="screenshot-plain">{{ plain }}</span>
    <span class="screenshot-previews">
      <span v-for="(id,index) in ids" :key="id" class="screenshot-preview">
        <a v-if="files[id]?.extension" class="screenshot-document" :class="{'invoice-drag-handle':invoiceDrag}" :href="files[id].url"
          :download="invoiceFilename(id,index)" :draggable="invoiceDrag" @click.stop @dragstart="dragInvoice($event,id,index)">下载 {{ files[id].extension.toUpperCase() }} 发票</a>
        <el-image v-else-if="files[id]" :src="files[id].url" :preview-src-list="imageUrls" preview-teleported fit="contain" @click.stop />
        <span v-else>{{ errors[id] || '正在加载附件…' }}</span>
        <button v-if="removable" type="button" :aria-label="files[id]?.extension ? '移除发票附件' : '移除截图'" @click.stop="$emit('remove',id)">×</button>
        <template v-if="invoiceDrag && files[id]?.fileExtension">
          <a v-if="!files[id].extension" class="invoice-drag-handle" :href="files[id].url" :download="invoiceFilename(id,index)" draggable="true"
            @click.stop @dragstart="dragInvoice($event,id,index)">下载或拖动截图</a>
          <template v-if="desktopDrag">
            <el-button v-if="!files[id].nativeToken" link :loading="files[id].preparing" @click.stop="prepareInvoice(id,index)">准备桌面拖出</el-button>
            <span v-else class="invoice-drag-handle" draggable="true" @dragstart="dragNativeInvoice($event,id)">拖到桌面或聊天窗口</span>
          </template>
        </template>
      </span>
    </span>
  </span>
</template>
<script setup>
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { screenshotIds,screenshotText } from '@/utils/screenshotReferences'
const props=defineProps({text:{type:String,default:''},showText:{type:Boolean,default:true},removable:Boolean,chatMessageId:[String,Number],chatKind:String,invoiceDrag:Boolean,invoiceOrderNo:String})
defineEmits(['remove'])
const ids=computed(()=>screenshotIds(props.text)),plain=computed(()=>screenshotText(props.text)),files=ref({}),errors=ref({})
const imageUrls = computed(() => ids.value.filter(id => files.value[id] && !files.value[id].extension).map(id => files.value[id].url))
const documentExtensions = {'application/pdf':'pdf','application/ofd':'ofd'}
const imageExtensions = {'image/png':'png','image/jpeg':'jpg'}
const desktopDrag = !!window.xinshiDesktop?.prepareInvoiceFile

function invoiceStem(index) {
  const orderNo = props.invoiceOrderNo?.replace(/[^a-z0-9.-]/gi, '_')
  return orderNo ? `${orderNo}-发票-${index+1}` : `发票-${index+1}`
}

function invoiceFilename(id, index) {
  return `${invoiceStem(index)}.${files.value[id].fileExtension}`
}

function dragInvoice(event, id, index) {
  if (!props.invoiceDrag) return
  event.stopPropagation()
  if (!event.dataTransfer) return
  const { blob, url } = files.value[id]
  const name = invoiceFilename(id, index)
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.clearData()
  event.dataTransfer.setData('DownloadURL', `${blob.type}:${name}:${url}`)
  event.dataTransfer.items.add(new File([blob], name, {type:blob.type}))
}

async function prepareInvoice(id, index) {
  const file = files.value[id]
  if (file.preparing) return
  file.preparing = true
  try {
    const base64 = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result).split(',')[1])
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(file.blob)
    })
    if (files.value[id] !== file) return
    const result = await window.xinshiDesktop.prepareInvoiceFile({
      name: invoiceStem(index), extension: file.fileExtension, base64,
    })
    file.nativeToken = result.token
  } catch {
    ElMessage.error('桌面拖出准备失败，请重试或先下载附件')
  } finally {
    file.preparing = false
  }
}

function dragNativeInvoice(event, id) {
  event.preventDefault()
  event.stopPropagation()
  window.xinshiDesktop.dragStatementFile(files.value[id].nativeToken)
}
let version=0
watch(() => [props.text, props.chatMessageId], async () => {
  const current = ++version
  for (const [id, file] of Object.entries(files.value)) {
    if (ids.value.includes(id)) continue
    URL.revokeObjectURL(file.url)
    delete files.value[id]
  }
  await Promise.all(ids.value.map(async id => {
    if (files.value[id]) return
    try {
      const blob = await api.get(`/editor-screenshots/${id}`, {
        responseType:'blob', timeout:60000, screenshotIds:[id],
        params:props.chatMessageId ? {chat_message_id:props.chatMessageId,chat_kind:props.chatKind || 'project'} : {},
      })
      if (current === version) {
        const extension = documentExtensions[blob.type]
        files.value[id] = {
          url: URL.createObjectURL(blob),
          blob: props.invoiceDrag ? blob : undefined,
          extension,
          fileExtension: extension || imageExtensions[blob.type],
        }
      }
    } catch (e) {
      if (current === version) errors.value[id] = [404,410].includes(e.response?.status || e.status) ? '附件已过期或不存在' : e.detail || '请重新打开记录以查看附件'
    }
  }))
}, {immediate:true})
onBeforeUnmount(() => {
  ++version
  for (const file of Object.values(files.value)) URL.revokeObjectURL(file.url)
})
</script>
<style scoped>
.screenshot-document { padding: 6px 30px 6px 8px; color: var(--el-color-primary); font-size: 13px; }
.invoice-drag-handle { cursor: grab; padding: 5px 8px; color: var(--el-color-primary); border: 1px solid var(--el-border-color); border-radius: 4px; }
.invoice-drag-handle:active { cursor: grabbing; }
</style>
<style scoped>.screenshot-text{display:inline-flex;flex-direction:column;max-width:100%;white-space:normal;vertical-align:top}.screenshot-plain{white-space:pre-wrap;overflow-wrap:anywhere}.screenshot-previews{display:flex;flex-wrap:wrap;gap:8px;margin-top:5px}.screenshot-preview{position:relative;display:inline-flex;flex-direction:column;max-width:280px;min-width:80px;font-size:11px;color:#94a3b8}.screenshot-preview .el-image{max-width:280px;height:130px;border:1px solid #e2e8f0;border-radius:6px}.screenshot-preview button{position:absolute;right:0;top:0;width:22px;height:22px;border:1px solid #cbd5e1;background:white;border-radius:4px;cursor:pointer}</style>
