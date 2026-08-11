<template>
  <span class="language-pair-text" :title="value || '-'">
    <span class="language-pair-text__primary">{{ summary.primary }}</span>
    <small v-if="summary.extraCount" class="language-pair-text__count">+{{ summary.extraCount }}</small>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { getLanguagePairSummary } from '@/utils/languagePair'

const props = defineProps({
  value: { type: String, default: '' }
})

const summary = computed(() => getLanguagePairSummary(props.value))
</script>

<style scoped>
.language-pair-text {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 5px;
  white-space: nowrap;
}

.language-pair-text__primary {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.language-pair-text__count {
  flex-shrink: 0;
  padding: 0 5px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  line-height: 18px;
}
</style>
