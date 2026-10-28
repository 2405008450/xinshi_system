<template><canvas ref="canvas" class="screenshot-annotations" :style="{ pointerEvents: tool === 'crop' ? 'none' : 'auto' }" @pointerdown.stop.prevent="begin" @pointermove.stop="move" @pointerup.stop="finish" @pointercancel.stop="cancel" /></template>
<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { drawScreenshotMark } from '@/utils/screenshotDrawing'
const props = defineProps({ source: Object, tool: String, color: String, size: Number, text: String, emoji: String })
const emit = defineEmits(['history-change', 'need-text'])
const canvas = ref(null), marks = []
let pending = null
function render() {
  if (!canvas.value || !props.source) return
  const output = canvas.value
  if (output.width !== props.source.width || output.height !== props.source.height) { output.width = props.source.width; output.height = props.source.height }
  const context = output.getContext('2d'); context.clearRect(0, 0, output.width, output.height); context.drawImage(props.source, 0, 0)
  marks.forEach(mark => drawScreenshotMark(context, mark))
  if (pending) drawScreenshotMark(context, pending)
}
function point(event) {
  const rect = canvas.value.getBoundingClientRect()
  return { x: Math.max(0, Math.min(canvas.value.width, (event.clientX - rect.left) / rect.width * canvas.value.width)), y: Math.max(0, Math.min(canvas.value.height, (event.clientY - rect.top) / rect.height * canvas.value.height)) }
}
function begin(event) {
  if (event.button !== 0 || props.tool === 'crop') return
  const start = point(event)
  if (props.tool === 'text' && !props.text?.trim()) { emit('need-text'); return }
  pending = { type: props.tool, start, end: start, points: [start], color: props.color, size: props.size, text: props.tool === 'emoji' ? props.emoji : props.text }
  canvas.value.setPointerCapture(event.pointerId)
  if (['text', 'emoji'].includes(props.tool)) { finish(); return }
  render()
}
function move(event) {
  if (!pending) return
  pending.end = point(event)
  if (pending.type === 'pen') pending.points.push(pending.end)
  render()
}
function finish() {
  if (!pending) return
  if (['text', 'emoji', 'pen'].includes(pending.type) || Math.hypot(pending.end.x - pending.start.x, pending.end.y - pending.start.y) > 2) marks.push(pending)
  pending = null; render(); emit('history-change', marks.length)
}
function cancel() { pending = null; render() }
function undo() { pending = null; marks.pop(); render(); emit('history-change', marks.length) }
function clear() { pending = null; marks.length = 0; render(); emit('history-change', 0) }
watch(() => props.source, async () => { marks.length = 0; pending = null; await nextTick(); render() })
onMounted(render)
defineExpose({ undo, clear, renderCanvas: () => { render(); return canvas.value } })
</script>
<style scoped>.screenshot-annotations{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair;touch-action:none}</style>
