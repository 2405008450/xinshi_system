<template>
  <div ref="areaRef" class="referral-evidence-cell" :class="{ 'is-dragging': dragging, 'is-disabled': disabled }"
    :tabindex="disabled ? -1 : 0" role="group" :aria-label="`${category.label}图片粘贴区`" :aria-disabled="disabled"
    @click="focusArea" @paste.stop="paste" @dragenter.prevent="dragEnter" @dragover.prevent @dragleave.prevent="dragLeave" @drop.prevent.stop="drop">
    <p class="referral-evidence-hint">在此粘贴截图、拖入图片或选择文件</p>
    <p class="referral-evidence-limit">PNG、JPEG、WebP，单张不超过5MB{{ category.key === 'qr' ? '；仅保留一张收款码' : '；支持多张' }}</p>
    <p v-if="category.key === 'qr' && drafts.length && images.length" class="referral-evidence-replacement">新收款码保存成功后替换旧码</p>
    <ReferralImages v-if="images.length" :images="images" editable :disabled="disabled" show-status @remove="$emit('remove', $event)" />
    <div v-if="drafts.length" class="referral-evidence-drafts">
      <div v-for="item in drafts" :key="item.id" class="referral-evidence-draft">
        <el-image :src="item.previewUrl" :preview-src-list="previewUrls" :initial-index="previewUrls.indexOf(item.previewUrl)" preview-teleported fit="contain" :alt="item.file.name" />
        <span class="referral-evidence-name" :title="item.file.name">{{ item.file.name }}</span>
        <el-tag size="small" :type="item.error ? 'danger' : 'info'" effect="plain">{{ item.error ? '上传失败' : '待上传' }}</el-tag>
        <span v-if="item.error" class="referral-evidence-error" role="alert">{{ item.error }}</span>
        <el-button link type="danger" :disabled="disabled" @click="$emit('remove-draft', item.id)">移除</el-button>
      </div>
    </div>
    <el-button size="small" :disabled="disabled" @click="fileRef?.click()">{{ category.key === 'qr' ? '选择／替换收款码' : '选择图片' }}</el-button>
    <input ref="fileRef" type="file" class="referral-evidence-file" accept="image/png,image/jpeg,image/webp" :multiple="category.key !== 'qr'" :disabled="disabled" @change="choose" />
    <span v-if="dragging" class="referral-evidence-drop">释放图片，添加至{{ category.label }}</span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { pasteReferralImages } from '@/utils/referralImages'
import ReferralImages from './ReferralImages.vue'

const props = defineProps({ category: { type: Object, required: true }, images: { type: Array, default: () => [] }, drafts: { type: Array, default: () => [] }, disabled: Boolean })
const emit = defineEmits(['files', 'remove', 'remove-draft'])
const areaRef = ref(), fileRef = ref(), dragDepth = ref(0)
const dragging = computed(() => !props.disabled && dragDepth.value > 0)
const previewUrls = computed(() => props.drafts.map(item => item.previewUrl))
const receive = files => { if (!props.disabled) emit('files', files) }
function paste(event) { pasteReferralImages(event, receive, { disabled: props.disabled }) }
function choose(event) { receive(Array.from(event.target.files || [])); event.target.value = '' }
function focusArea(event) {
  if (!props.disabled && !event.target.closest('button, input, .el-image')) areaRef.value?.focus({ preventScroll: true })
}
function dragEnter(event) { if (!props.disabled && Array.from(event.dataTransfer?.types || []).includes('Files')) dragDepth.value++ }
function dragLeave() { dragDepth.value = Math.max(0, dragDepth.value - 1) }
function drop(event) { dragDepth.value = 0; receive(Array.from(event.dataTransfer?.files || [])) }
</script>

<style scoped>
.referral-evidence-cell{position:relative;width:100%;min-width:0;box-sizing:border-box;border:1px dashed #cbd5e1;border-radius:8px;padding:12px;background:#fff;cursor:text;outline:none}
.referral-evidence-cell:focus,.referral-evidence-cell:focus-within,.referral-evidence-cell.is-dragging{border-color:var(--el-color-primary);box-shadow:0 0 0 2px var(--el-color-primary-light-9)}
.referral-evidence-cell.is-disabled{cursor:default}.referral-evidence-hint{margin:0;color:#334155;font-size:13px;line-height:1.5}.referral-evidence-limit{margin:4px 0 10px;color:#64748b;font-size:12px;line-height:1.5}
.referral-evidence-drafts{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0}.referral-evidence-draft{width:132px;max-width:100%;display:flex;flex-direction:column;align-items:center;gap:5px}
.referral-evidence-draft .el-image{width:132px;max-width:100%;height:118px;border:1px solid #e2e8f0;border-radius:6px}.referral-evidence-name{width:100%;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:12px}.referral-evidence-error{color:#b91c1c;font-size:12px;overflow-wrap:anywhere;line-height:1.5}.referral-evidence-replacement{color:#92400e;font-size:12px;margin:0 0 10px}
.referral-evidence-file{display:none}.referral-evidence-drop{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:var(--el-color-primary-light-9);border-radius:8px;color:var(--el-color-primary);pointer-events:none}.referral-evidence-cell>.el-button{margin-top:8px}
</style>
