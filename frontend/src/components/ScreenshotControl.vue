<template>
  <div class="screenshot-control">
    <el-button text :loading="capturing" :title="`截图（${label}）`" :aria-label="`截图（${label}）`" @click="capture"><el-icon><Camera /></el-icon><span>截图</span></el-button>
    <el-popover trigger="click" placement="bottom-end" :width="320" @show="draft = shortcut">
      <template #reference><el-button text aria-label="设置截图快捷键" title="设置截图快捷键"><el-icon><Setting /></el-icon></el-button></template>
      <strong>截图快捷键</strong>
      <p class="capture-help">点击下方输入框，再按下快捷键组合。</p>
      <el-input :model-value="shortcutLabel(draft)" readonly aria-label="录制截图快捷键" @keydown.stop="record" />
      <p class="capture-help">默认 Alt+A；仅在系统窗口获得焦点时生效。{{ nativeCapture ? '桌面版直接截取鼠标所在屏幕。' : '浏览器版需选择窗口或屏幕；免询问截屏请使用 Windows 桌面入口。' }}</p>
      <el-button size="small" @click="draft = DEFAULT_SCREENSHOT_SHORTCUT">恢复默认</el-button>
      <el-button size="small" type="primary" @click="save">保存</el-button>
    </el-popover>
  </div>
  <DraggableFormDialog v-model="preview" title="截图预览" width="min(1080px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close @closed="release">
    <p class="capture-help">先框选截图区域，再选择下方工具标注；未框选时使用整张截图。完成后可复制或下载。</p>
    <div ref="surface" class="capture-surface" @pointerdown.prevent="beginSelection" @pointermove="moveSelection" @pointerup="finishSelection" @pointercancel="finishSelection">
      <img v-if="imageUrl" :src="imageUrl" alt="截图预览" draggable="false" />
      <ScreenshotAnnotator ref="annotator" :source="original" :tool="tool" :color="color" :size="strokeSize" :text="annotationText" :emoji="emoji" @history-change="annotationCount = $event" @need-text="ElMessage.info('请先在工具栏输入标注文字')" />
      <div v-if="selection" class="capture-selection" :style="selectionStyle" />
    </div>
    <template #footer>
      <div class="capture-toolbar" aria-label="截图编辑工具栏">
        <el-button v-for="item in tools" :key="item.key" :type="tool === item.key ? 'primary' : 'default'" :aria-pressed="tool === item.key" :title="item.label" @click="tool = item.key">{{ item.icon }} {{ item.label }}</el-button>
        <label class="capture-color">颜色 <input v-model="color" type="color" aria-label="标注颜色" /></label>
        <label class="capture-size">粗细 <select v-model.number="strokeSize" aria-label="标注粗细"><option :value="2">细</option><option :value="4">中</option><option :value="8">粗</option></select></label>
        <el-input v-if="tool === 'text'" v-model="annotationText" class="capture-text" placeholder="输入标注文字，然后点击图片放置" aria-label="标注文字" maxlength="500" />
        <select v-if="tool === 'emoji'" v-model="emoji" aria-label="选择表情"><option v-for="item in ['😀','👍','✅','❌','⭐','❗','❤️']" :key="item">{{ item }}</option></select>
        <el-button :disabled="!annotationCount" @click="annotator?.undo()">↶ 撤销</el-button>
        <el-button :disabled="!annotationCount" @click="annotator?.clear()">清除标注</el-button>
        <el-button :disabled="!selection" @click="selection = null">取消框选</el-button>
        <el-button @click="download">⇩ 下载</el-button>
        <el-button @click="pin">📌 贴图</el-button>
        <el-button @click="preview = false">✕ 取消</el-button>
        <el-button type="primary" @click="complete">✓ 完成并复制</el-button>
      </div>
    </template>
  </DraggableFormDialog>
  <DraggableFormDialog v-model="pinned" title="截图贴图 · 可拖动查看" width="min(560px, calc(100vw - 32px))" top="10vh" append-to-body :modal="false" :lock-scroll="false" :close-on-click-modal="false" destroy-on-close @closed="releasePin">
    <img v-if="pinUrl" :src="pinUrl" class="capture-pinned" alt="已标注的截图贴图" />
  </DraggableFormDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ScreenshotAnnotator from '@/components/common/ScreenshotAnnotator.vue'
import { Camera, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { DEFAULT_SCREENSHOT_SHORTCUT, readScreenshotShortcut, shortcutFromEvent, shortcutLabel } from '@/utils/screenshotShortcut'

const nativeCapture = typeof window.xinshiDesktop?.captureScreen === 'function'
const actor = () => localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
const shortcut = ref(readScreenshotShortcut(localStorage, actor())), draft = ref(shortcut.value)
const label = computed(() => shortcutLabel(shortcut.value))
const capturing = ref(false), preview = ref(false), imageUrl = ref(''), surface = ref(null), selection = ref(null)
const annotator = ref(null), annotationCount = ref(0), tool = ref('crop'), color = ref('#ef4444'), strokeSize = ref(4), annotationText = ref(''), emoji = ref('😀')
const pinned = ref(false), pinUrl = ref('')
const tools = [{key:'crop',label:'框选',icon:'⌗'},{key:'rectangle',label:'方框',icon:'□'},{key:'ellipse',label:'圆框',icon:'○'},{key:'emoji',label:'表情',icon:'☺'},{key:'arrow',label:'箭头',icon:'↗'},{key:'pen',label:'画笔',icon:'✎'},{key:'mosaic',label:'马赛克',icon:'▦'},{key:'text',label:'文字',icon:'T'}]
let original, start, disposed = false, activeStream, activeVideo
const selectionStyle = computed(() => {
  const box = selection.value
  return { left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }
})
function record(event) {
  if (event.code === 'Tab') return
  event.preventDefault()
  const value = shortcutFromEvent(event)
  if (value) draft.value = value
  else if (!['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)) ElMessage.info('请使用修饰键加字母、数字或功能键，并避开浏览器常用快捷键')
}
function save() {
  try {
    localStorage.setItem(`screenshot-shortcut:${encodeURIComponent(actor())}`, draft.value)
    shortcut.value = draft.value
    ElMessage.success(`截图快捷键已设为 ${label.value}`)
  } catch { ElMessage.error('无法保存快捷键，请检查浏览器存储') }
}
function hotkey(event) {
  if (shortcutFromEvent(event) !== shortcut.value || capturing.value || preview.value) return
  event.preventDefault(); event.stopPropagation(); void capture()
}
function sync(event) {
  if (event.key === `screenshot-shortcut:${encodeURIComponent(actor())}`) shortcut.value = readScreenshotShortcut(localStorage, actor())
}
async function capture() {
  if (capturing.value || preview.value) return
  if (!nativeCapture && !navigator.mediaDevices?.getDisplayMedia) { ElMessage.warning('当前浏览器不支持屏幕截图，请使用支持屏幕共享的浏览器'); return }
  const user = actor()
  capturing.value = true
  try {
    let canvas
    if (nativeCapture) {
      const url = await window.xinshiDesktop.captureScreen()
      if (disposed || actor() !== user) return
      if (!url.startsWith('data:image/png;base64,')) throw Error('桌面截图格式无效')
      const image = new Image()
      await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = () => reject(Error('无法读取桌面截图')); image.src = url })
      canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight
      canvas.getContext('2d').drawImage(image, 0, 0)
    } else {
    activeStream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'monitor' }, audio: false })
    if (disposed || actor() !== user) return
    activeVideo = document.createElement('video')
    activeVideo.srcObject = activeStream; activeVideo.muted = true
    await activeVideo.play()
    if (!activeVideo.videoWidth || !activeVideo.videoHeight) throw Error('未获取到屏幕画面，请重试')
    canvas = document.createElement('canvas')
    canvas.width = activeVideo.videoWidth; canvas.height = activeVideo.videoHeight
    canvas.getContext('2d').drawImage(activeVideo, 0, 0)
    }
    if (disposed || actor() !== user) return
    original = canvas
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw Error('截图生成失败，请重试')
    if (disposed || actor() !== user) return
    releaseUrl(); imageUrl.value = URL.createObjectURL(blob); selection.value = null; tool.value = 'crop'; annotationCount.value = 0; preview.value = true
  } catch (error) {
    if (!disposed && !['NotAllowedError', 'AbortError'].includes(error.name)) ElMessage.error(error.message || '截图失败，请重试')
  } finally {
    activeStream?.getTracks().forEach(track => track.stop()); activeStream = null
    if (activeVideo) { activeVideo.srcObject = null; activeVideo = null }
    capturing.value = false
  }
}
function point(event) {
  const rect = surface.value.getBoundingClientRect()
  return { x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)), y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)) }
}
function beginSelection(event) {
  if (event.button !== 0 || tool.value !== 'crop') return
  start = point(event); surface.value.setPointerCapture(event.pointerId); selection.value = null
}
function moveSelection(event) {
  if (!start) return
  const end = point(event)
  selection.value = { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(start.x - end.x), height: Math.abs(start.y - end.y) }
}
function finishSelection() {
  start = null
  if (selection.value && (selection.value.width < 0.005 || selection.value.height < 0.005)) selection.value = null
}
async function exportBlob() {
  if (!original) throw Error('请先截图')
  const edited = annotator.value?.renderCanvas() || original
  const box = selection.value
  if (!box) return new Promise(resolve => edited.toBlob(resolve, 'image/png'))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(box.width * original.width)); canvas.height = Math.max(1, Math.round(box.height * original.height))
  canvas.getContext('2d').drawImage(edited, Math.round(box.x * original.width), Math.round(box.y * original.height), canvas.width, canvas.height, 0, 0, canvas.width, canvas.height)
  return new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
}
async function copy() {
  try {
    if (!navigator.clipboard?.write || !window.ClipboardItem) throw Error('当前浏览器无法复制图片，请下载截图')
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': exportBlob().then(blob => { if (!blob) throw Error('截图生成失败'); return blob }) })])
    ElMessage.success('截图已复制，可粘贴使用'); return true
  } catch (error) { ElMessage.warning(error.message || '无法复制图片，请下载截图'); return false }
}
async function download() {
  try {
    const blob = await exportBlob()
    if (!blob) throw Error('截图生成失败')
    const url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url; link.download = '截图.png'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) { ElMessage.error(error.message || '截图下载失败') }
}
async function complete() { if (await copy()) preview.value = false }
async function pin() {
  try {
    const blob = await exportBlob()
    if (!blob) throw Error('截图生成失败')
    releasePin(); pinUrl.value = URL.createObjectURL(blob); pinned.value = true; preview.value = false
  } catch (error) { ElMessage.error(error.message || '无法生成贴图') }
}
function releasePin() { if (pinUrl.value) URL.revokeObjectURL(pinUrl.value); pinUrl.value = '' }
function releaseUrl() { if (imageUrl.value) URL.revokeObjectURL(imageUrl.value); imageUrl.value = '' }
function release() { releaseUrl(); original = null; selection.value = null; start = null }
onMounted(() => { window.addEventListener('keydown', hotkey); window.addEventListener('storage', sync) })
onBeforeUnmount(() => {
  disposed = true; window.removeEventListener('keydown', hotkey); window.removeEventListener('storage', sync)
  activeStream?.getTracks().forEach(track => track.stop()); release(); releasePin()
})
</script>

<style scoped>
.screenshot-control { display: inline-flex; align-items: center; gap: 0; }
.screenshot-control .el-button + .el-button { margin-left: 0; padding: 6px; }
.screenshot-control .el-icon { margin-right: 4px; }
.capture-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: 8px; text-align: left; }
.capture-toolbar .el-button { margin: 0; }
.capture-color, .capture-size { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.capture-color input { width: 32px; height: 28px; padding: 0; border: 1px solid var(--el-border-color); cursor: pointer; }
.capture-text { width: 260px; }
.capture-pinned { display: block; max-width: 100%; max-height: 70vh; margin: auto; object-fit: contain; }
.capture-help { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.capture-surface { position: relative; width: fit-content; max-width: 100%; margin: auto; line-height: 0; cursor: crosshair; touch-action: none; user-select: none; }
.capture-surface img { display: block; max-width: 100%; max-height: 60vh; object-fit: contain; }
.capture-selection { position: absolute; border: 2px solid var(--el-color-primary); background: #409eff20; pointer-events: none; box-sizing: border-box; }
</style>
