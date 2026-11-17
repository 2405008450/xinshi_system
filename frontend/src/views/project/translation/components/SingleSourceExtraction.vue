<template>
  <div class="single-source-extraction">
    <el-button :loading="busy" :disabled="disabled || !path.trim()" @click="extract">提取文件名与工作量</el-button>
    <span v-if="busy" role="status">{{ stage }}</span>
    <template v-if="showLocalChoices">
      <small>请选择路径所指的同一个文件或文件夹，授权浏览器读取。</small>
      <el-button size="small" :disabled="busy || disabled" @click="fileInput.click()">选择本地文件</el-button>
      <el-button size="small" :disabled="busy || disabled" @click="chooseFolder">选择本地文件夹</el-button>
    </template>
    <input ref="fileInput" type="file" hidden @change="chooseFile" />
    <el-alert v-if="notice" :title="notice" :type="noticeType" :closable="false" show-icon>
      <template v-if="showLanLink" #default>
        <el-link href="https://oa.xinshify.com.cn/" target="_blank" rel="noopener noreferrer" type="primary">打开局域网版本：https://oa.xinshify.com.cn/</el-link>
      </template>
    </el-alert>
    <div v-if="result" class="single-source-counts">
      <span v-for="metric in documentCountMetrics" :key="metric.key">
        {{ metric.label }} {{ result[metric.key]?.toLocaleString('zh-CN') ?? '—' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { documentCountMetrics, documentCountValues, inspectSingleSharedSource, uploadDocumentCount, waitForDocumentCount } from '@/api/documentWordCounts'
import { getLocalizedErrorMessage, getRawErrorDetail } from '@/utils/errorMessages'
import { normalizeFolderRootInput } from '@/utils/translationFolderPaths'
import { translationFileNameError } from '@/utils/translationFileName'

const props = defineProps({
  path: { type: String, default: '' },
  disabled: Boolean,
  folderImported: Boolean,
  canApplyCounts: { type: Function, required: true },
})
const emit = defineEmits(['extracted'])
const wrongFolder = '本选项卡只提取一级文件夹里的一个文件。目录有多个文件或包含子文件夹时，请到「新增母子订单」选项卡处理。'
const countableFile = /\.(docx?|xlsx?|pptx?|pdf|txt)$/i
const ignoredFile = /^(?:\.ds_store|desktop\.ini|thumbs\.db|~\$.*)$/i
const fileInput = ref(null)
const busy = ref(false)
const showLocalChoices = ref(false)
const stage = ref('')
const notice = ref('')
const showLanLink = ref(false)
const noticeType = ref('info')
const result = ref(null)
let controller

const normalizedPath = value => normalizeFolderRootInput(value).replaceAll('/', '\\')
const comparablePath = value => normalizedPath(value).replace(/\\+$/, '').toLowerCase()
function publish(message, type = 'warning') {
  notice.value = message
  noticeType.value = type
}

function reset() {
  controller?.abort()
  busy.value = false
  showLocalChoices.value = false
  notice.value = ''
  showLanLink.value = false
  result.value = null
}
watch(() => props.path, reset, { flush: 'sync' })
onBeforeUnmount(reset)

function verifyLocalSelection(handle, path) {
  const expected = comparablePath(path)
  if (handle.name.toLowerCase() !== expected.split('\\').at(-1)
      || (handle.path && comparablePath(handle.path) !== expected)) {
    throw new Error('选择的文件或文件夹与原文路径不一致')
  }
}

async function chooseFolder() {
  if (!window.showDirectoryPicker) {
    publish('当前浏览器无法核对目录结构。可使用桌面客户端，或输入具体文件的完整路径后选择该文件。')
    return
  }
  await run(async path => {
    const directory = await window.showDirectoryPicker({ mode: 'read' })
    verifyLocalSelection(directory, path)
    let file
    for await (const entry of directory.values()) {
      if (entry.kind === 'directory') throw new Error(wrongFolder)
      if (entry.kind !== 'file' || ignoredFile.test(entry.name)) continue
      if (file) throw new Error(wrongFolder)
      file = entry
    }
    if (!file) throw new Error('原文路径中没有可读取的文件')
    try {
      return { name: file.name, file: await file.getFile() }
    } catch {
      return { name: file.name, message: '无法读取文件正文' }
    }
  })
}

function chooseFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) void run(path => {
    verifyLocalSelection(file, path)
    return { name: file.name, file }
  })
}

function extract() {
  if (props.folderImported) {
    publish(wrongFolder)
    return
  }
  const path = normalizedPath(props.path)
  if (path.startsWith('\\\\')) {
    void run((value, signal) => inspectSingleSharedSource(value, signal))
  } else if (/^[a-z]:\\/i.test(path) && !/[\x00-\x1f:*?"<>|]/.test(path.slice(2))
    && !path.split('\\').some(part => part === '.' || part === '..')) {
    if (window.xinshiDesktop?.inspectSingleTranslationSource) {
      void run(async value => {
        const source = await window.xinshiDesktop.inspectSingleTranslationSource(value)
        if (!source) return null
        return { name: source.name, message: source.message,
          file: source.bytes ? new File([source.bytes], source.name) : null }
      })
    } else {
      showLocalChoices.value = true
    }
  } else {
    publish('请填写本地文件、文件夹或 UNC 共享的完整路径。')
  }
}

async function run(readSource) {
  if (busy.value || props.disabled) return
  controller = new AbortController()
  const { signal } = controller
  const path = normalizedPath(props.path)
  busy.value = true
  stage.value = '正在提取文件名…'
  notice.value = ''
  showLanLink.value = false
  result.value = null
  let name
  try {
    const source = await readSource(path, signal)
    if (signal.aborted || !source) return
    const filenameError = translationFileNameError(source.name)
    if (filenameError) throw new Error(filenameError)
    name = source.name
    showLocalChoices.value = false
    let jobId = source.job_id
    let message = source.message
    if (source.file) {
      if (!countableFile.test(name)) message = '该格式暂不支持自动统计'
      else if (source.file.size > 50 * 1024 ** 2) message = '单文件超过 50 MB'
      else {
        stage.value = '正在提交文件统计…'
        jobId = (await uploadDocumentCount([source.file], signal)).job_id
      }
    }
    let values = {}
    if (jobId) {
      stage.value = '正在提取字数、字符数和中朝统计…'
      const [file] = await waitForDocumentCount(jobId, signal)
      values = documentCountValues(file)
      message = file?.message
    }
    if (signal.aborted) return
    if (!Object.keys(values).length) {
      emit('extracted', { name })
      publish('已填入文件名。' + (message || '未取得有效统计，请手动填写。'))
      return
    }
    result.value = values
    const apply = props.canApplyCounts(values)
    emit('extracted', { name, values: apply ? values : undefined })
    if (!apply) publish('已填入文件名。现有我司统计使用其他计量单位，请先调整，再重新提取。')
    else if (Object.keys(values).length < documentCountMetrics.length) publish('已填入文件名和可取得的统计。其余项目请手动补填。')
    else publish('已填入项目名称和我司统计。', 'success')
  } catch (error) {
    if (signal.aborted || error.name === 'AbortError') return
    // 云端无法访问局域网共享目录；保留权限校验、目录结构等业务错误的原有提示。
    const rawMessage = String(getRawErrorDetail(error) ?? error.message ?? '')
    if (!name && path.startsWith('\\\\')
      && ['www.oa.xinshify.com.cn', '43.132.156.72'].includes(window.location.hostname)
      && /no such file|\[errno\s+\d+\]|\[winerror\s+\d+\]|permission denied|路径不存在|无法访问|找不到.*路径/i.test(rawMessage)) {
      showLanLink.value = true
      publish('当前使用的是云端版本，无法读取局域网共享文件夹。请连接公司局域网，将系统链接更换为 https://oa.xinshify.com.cn/，登录后重新执行提取。切换前请先保存已填写的内容。', 'warning')
      return
    }
    if (name) emit('extracted', { name })
    const message = getLocalizedErrorMessage(error, name ? '工作量统计失败' : '读取原文路径失败')
    publish(name ? '已填入文件名。' + message : message, name ? 'warning' : 'error')
  } finally {
    if (!signal.aborted) busy.value = false
  }
}
</script>

<style scoped>
.single-source-extraction { width: 100%; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
.single-source-extraction small, .single-source-counts { width: 100%; }
.single-source-counts { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--el-text-color-regular); }
</style>
